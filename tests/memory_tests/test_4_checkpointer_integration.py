import uuid
import sqlite3
from pathlib import Path

from agent.agent import create_procurement_workflow
from agent.utils.state import ProcurementState


def _assert_checkpoints_exist(sqlite_path: Path, thread_id: str) -> None:
    """Best-effort check: er is data in sqlite gekoppeld aan dit thread_id."""
    conn = sqlite3.connect(sqlite_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]

        # Zoek in alle tabellen naar kolommen die op thread id lijken
        found_rows = 0
        for t in tables:
            cur.execute(f"PRAGMA table_info({t})")
            cols = [r[1] for r in cur.fetchall()]
            # Veel voorkomende kolomnamen in langgraph sqlite checkpoint schema's
            candidate_cols = [c for c in cols if c in {"thread_id", "thread", "config", "checkpoint", "metadata"}]
            if not candidate_cols:
                continue

            for c in candidate_cols:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {t} WHERE CAST({c} AS TEXT) LIKE ?", (f"%{thread_id}%",))
                    cnt = cur.fetchone()[0]
                    found_rows += cnt
                except Exception:
                    # Sommige kolommen zijn binary/JSON; query kan falen afhankelijk van dialect/type
                    pass

        assert found_rows > 0, f"Geen checkpoint rows gevonden voor thread_id={thread_id}"
    finally:
        conn.close()


def run_checkpointer_integration() -> None:
    workflow = create_procurement_workflow()

    # Gebruik vaste thread_id voor resume
    thread_id = str(uuid.uuid4())[:8].upper()
    config = {"configurable": {"thread_id": thread_id}}

    # 1) Start run
    initial_state = ProcurementState(thread_id=thread_id)
    result1 = workflow.invoke(initial_state, config=config)
    if isinstance(result1, dict):
        result1 = ProcurementState(**result1)

    # Verwacht: of geen proposals (klaar), of waiting human input
    proposals = result1.data.get("reorder_proposals", [])
    if not proposals:
        print("[INFO] Geen reorder_proposals. Integratietest kan niet door naar approval-pad met huidige data.")
        print("[INFO] Thread wel aangemaakt:", thread_id)
    else:
        assert result1.step == "awaiting_human_input", (
            f"Verwacht awaiting_human_input, kreeg step={result1.step}, status={result1.status}"
        )
        print("[OK] Workflow gepauzeerd op human approval.")

        # 2) Hervat zelfde thread met human decision
        # approve alle draft orders op index
        draft_orders = result1.data.get("draft_orders", [])
        approved_indices = list(range(len(draft_orders)))

        resumed_data = result1.model_dump()
        resumed_data.update({
            "approved_orders": approved_indices,
            "rejection_reasons": {},
            "approval_decision": "approved",
            "approved_by": "integration_test_user",
            "approval_reason": "Integration test approval",
        })
        resumed_state = ProcurementState(**resumed_data)

        result2 = workflow.invoke(resumed_state, config=config)
        if isinstance(result2, dict):
            result2 = ProcurementState(**result2)

        # Na process_approval zou flow einde bereikt moeten hebben
        assert result2.status in {"ok", "approved", "complete", "cancelled"} or result2.step in {"complete", "end"}, (
            f"Onverwachte eindstatus: step={result2.step}, status={result2.status}, message={result2.message}"
        )
        print("[OK] Workflow hervat en afgerond na human approval.")

    # 3) Check sqlite checkpoint data
    sqlite_path = (Path(__file__).parent / "db" / "checkpoints.sqlite").resolve()
    assert sqlite_path.exists(), f"checkpoints sqlite niet gevonden: {sqlite_path}"
    _assert_checkpoints_exist(sqlite_path, thread_id)
    print(f"[OK] Checkpoint data gevonden voor thread_id={thread_id}")
    print("[SUCCESS] Checkpointer integratietest geslaagd.")


if __name__ == "__main__":
    run_checkpointer_integration()
