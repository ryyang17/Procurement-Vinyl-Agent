import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Paden ────────────────────────────────────────────────────────────────────
_DB_DIR = Path(__file__).parent.parent.parent / "db"
DECISION_LOG_DB_PATH = _DB_DIR / "decision_log.db"
# Oud JSON-pad (alleen nog gebruikt als fallback-referentie)
MEMORY_DB_PATH = _DB_DIR / "decision_log.json"


# ── Database helpers ──────────────────────────────────────────────────────────

def _ensure_db() -> None:
    """Maak de SQLite-database en tabel aan als ze nog niet bestaan."""
    DECISION_LOG_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DECISION_LOG_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decision_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                type          TEXT    NOT NULL,
                supplier_id   INTEGER,
                supplier_name TEXT,
                reason        TEXT,
                po_id         INTEGER,
                context       TEXT,
                actor         TEXT    NOT NULL DEFAULT 'system'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_supplier  ON decision_log (supplier_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_type      ON decision_log (type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON decision_log (timestamp)")
        conn.commit()


@contextmanager
def _get_conn():
    """Context-manager die een SQLite-verbinding opent en automatisch sluit."""
    _ensure_db()
    conn = sqlite3.connect(DECISION_LOG_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Zet een SQLite-rij om naar een dictionary (context wordt teruggezet naar dict)."""
    d = dict(row)
    try:
        d["context"] = json.loads(d["context"]) if d.get("context") else {}
    except (json.JSONDecodeError, TypeError):
        d["context"] = {}
    return d


# ── Publieke functies (zelfde interface als voorheen) ─────────────────────────

def log_decision(
    decision_type: str,
    supplier_id: Optional[int] = None,
    supplier_name: Optional[str] = None,
    reason: Optional[str] = None,
    po_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """Sla een beslissing op in de SQLite-database en geef het event-dict terug."""

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": decision_type,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "reason": reason,
        "po_id": po_id,
        "context": context or {},
        "actor": actor,
    }

    with _get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO decision_log
               (timestamp, type, supplier_id, supplier_name, reason, po_id, context, actor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event["timestamp"],
                event["type"],
                event["supplier_id"],
                event["supplier_name"],
                event["reason"],
                event["po_id"],
                json.dumps(event["context"], ensure_ascii=False),
                event["actor"],
            ),
        )
        conn.commit()
        event["id"] = cursor.lastrowid

    return event


def get_supplier_history(supplier_id: int, days: int = 30) -> List[Dict[str, Any]]:
    """Haal alle beslissingen op voor een leverancier binnen het opgegeven aantal dagen."""

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM decision_log
               WHERE supplier_id = ?
                 AND timestamp >= ?
               ORDER BY timestamp ASC""",
            (supplier_id, cutoff),
        ).fetchall()

    return [_row_to_dict(r) for r in rows]


def get_last_rejection_reason(supplier_id: int) -> Optional[str]:
    """Geef de meest recente afwijzingsreden voor een leverancier terug."""

    with _get_conn() as conn:
        row = conn.execute(
            """SELECT reason FROM decision_log
               WHERE supplier_id = ?
                 AND type = 'supplier_rejected'
                 AND reason IS NOT NULL
               ORDER BY timestamp DESC
               LIMIT 1""",
            (supplier_id,),
        ).fetchone()

    return row["reason"] if row else None


def get_recent_rejections(supplier_id: int, days: int = 7) -> List[Dict[str, Any]]:
    """Haal recente afwijzingen op voor een leverancier."""

    history = get_supplier_history(supplier_id, days=days)
    return [e for e in history if e["type"] == "supplier_rejected"]


def get_all_decisions(limit: int = 100) -> List[Dict[str, Any]]:
    """Haal de laatste `limit` beslissingen op, meest recent eerst."""

    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM decision_log
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    return [_row_to_dict(r) for r in rows]


def get_supplier_summary(supplier_id: int) -> Dict[str, Any]:
    """Geef een samenvatting terug van goedkeuringen en afwijzingen voor een leverancier."""

    history = get_supplier_history(supplier_id, days=999)

    approvals = [e for e in history if e["type"] == "supplier_approved"]
    rejections = [e for e in history if e["type"] == "supplier_rejected"]

    return {
        "approval_count": len(approvals),
        "rejection_count": len(rejections),
        "last_decision": history[-1] if history else None,
        "last_rejection_reason": get_last_rejection_reason(supplier_id),
        "rejection_reasons": [e.get("reason") for e in rejections if e.get("reason")],
    }


def update_supplier_performance_on_rejection(supplier_id: int, rejection_reason: str) -> None:
    """Pas de leveranciersprestaties aan op basis van de afwijzingsreden."""

    perf_path = Path(__file__).parent.parent.parent / "db" / "supplier_performance.json"

    try:
        with open(perf_path, "r", encoding="utf-8") as f:
            performances = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    supplier_perf = next((p for p in performances if p.get("supplier_id") == supplier_id), None)
    if not supplier_perf:
        return

    reason_lower = rejection_reason.lower()

    delivery_keywords     = ["vertraging", "laat", "late", "delay", "leveringstijd", "levering"]
    quality_keywords      = ["kwaliteit", "quality", "defect", "beschadigd", "slecht"]
    availability_keywords = ["niet bereikbaar", "unavailable", "onbereikbaar", "geen contact", "niet beschikbaar"]

    updated = False

    if any(kw in reason_lower for kw in delivery_keywords):
        supplier_perf["late_deliveries"] = supplier_perf.get("late_deliveries", 0) + 1
        total_orders   = supplier_perf.get("total_orders", 1)
        late_deliveries = supplier_perf["late_deliveries"]
        supplier_perf["reliability_score"] = max(0.0, (total_orders - late_deliveries) / total_orders)
        updated = True

    if any(kw in reason_lower for kw in quality_keywords):
        current_score = supplier_perf.get("reliability_score", 1.0)
        supplier_perf["reliability_score"] = max(0.0, current_score - 0.05)
        updated = True

    if any(kw in reason_lower for kw in availability_keywords):
        supplier_perf["temporarily_unavailable"] = True
        supplier_perf["unavailable_since"] = datetime.now(timezone.utc).isoformat()
        current_score = supplier_perf.get("reliability_score", 1.0)
        supplier_perf["reliability_score"] = max(0.0, current_score - 0.10)
        updated = True

    if updated:
        supplier_perf["evaluation_date"]       = datetime.now(timezone.utc).isoformat()
        supplier_perf["last_rejection_reason"] = rejection_reason

        with open(perf_path, "w", encoding="utf-8") as f:
            json.dump(performances, f, ensure_ascii=False, indent=2)
