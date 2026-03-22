from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent.agent import create_procurement_workflow, get_checkpointer

app = FastAPI(title="Procurement Vinyl Agent API")
workflow = create_procurement_workflow()


class ApprovalDecisionRequest(BaseModel):
    approved_indices: List[int] = Field(default_factory=list)
    rejection_reasons_by_index: Dict[int, str] = Field(default_factory=dict)
    approved_by: str = "manager"
    decision: Optional[str] = None


def _safe_state(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    # Fallback for pydantic/dataclass-like objects
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {"raw_state": str(value)}


def _thread_config(thread_id: str) -> Dict[str, Dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def _get_thread_state(thread_id: str) -> Dict[str, Any]:
    snapshot = workflow.get_state(_thread_config(thread_id))
    values = getattr(snapshot, "values", None)
    if not values:
        return {}
    if isinstance(values, dict):
        return values
    return _safe_state(values)


def _extract_draft_orders(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(state, dict):
        return []

    data = state.get("data")
    if isinstance(data, dict):
        draft_orders = data.get("draft_orders", [])
        if isinstance(draft_orders, list):
            return draft_orders

    draft_orders = state.get("draft_orders", [])
    if isinstance(draft_orders, list):
        return draft_orders
    return []


def _is_pending_approval(state: Dict[str, Any]) -> bool:
    if not state:
        return False

    if bool(state.get("awaiting_human_approval")):
        return True

    step = str(state.get("step", "")).lower()
    status = str(state.get("status", "")).lower()
    if step == "awaiting_human_input" and status in {"awaiting_approval", "awaiting_path_selection"}:
        return True

    return False


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/predict")
async def predict(request: Request):
    try:
        payload = await request.json()
        input_state = payload.get("state", {}) if isinstance(payload, dict) else {}

        # Keep each run in a persistent thread so checkpoints can be resumed.
        payload_thread_id = payload.get("thread_id") if isinstance(payload, dict) else None
        thread_id = payload_thread_id or input_state.get("thread_id") or str(uuid.uuid4())
        if isinstance(input_state, dict):
            input_state["thread_id"] = thread_id

        # LangGraph accepts plain dict input for most workflows
        result = workflow.invoke(input_state, config=_thread_config(thread_id))

        return JSONResponse(content={"thread_id": thread_id, "state": _safe_state(result)})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"{type(exc).__name__}: {exc}"},
        )


@app.get("/checkpoints/pending")
async def get_pending_checkpoints(limit: int = 100):
    try:
        saver = get_checkpointer()
        seen_thread_ids = set()
        pending_items = []

        for checkpoint_tuple in saver.list(None):
            thread_id = (
                checkpoint_tuple.config
                .get("configurable", {})
                .get("thread_id")
            )
            if not thread_id or thread_id in seen_thread_ids:
                continue

            seen_thread_ids.add(thread_id)
            state = _get_thread_state(thread_id)
            if not _is_pending_approval(state):
                continue

            draft_orders = _extract_draft_orders(state)
            pending_items.append(
                {
                    "thread_id": thread_id,
                    "step": state.get("step"),
                    "status": state.get("status"),
                    "message": state.get("message"),
                    "approval_requested_at": state.get("approval_requested_at"),
                    "updated_at": checkpoint_tuple.checkpoint.get("ts") if checkpoint_tuple.checkpoint else None,
                    "draft_orders_count": len(draft_orders),
                    "draft_orders": draft_orders,
                }
            )

            if len(pending_items) >= max(limit, 1):
                break

        return JSONResponse(content={"items": pending_items, "count": len(pending_items)})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"{type(exc).__name__}: {exc}"},
        )


@app.get("/checkpoints/{thread_id}")
async def get_checkpoint_state(thread_id: str):
    try:
        state = _get_thread_state(thread_id)
        if not state:
            return JSONResponse(status_code=404, content={"error": f"Geen checkpoint gevonden voor thread_id={thread_id}"})

        return JSONResponse(
            content={
                "thread_id": thread_id,
                "state": state,
                "pending": _is_pending_approval(state),
                "draft_orders": _extract_draft_orders(state),
            }
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"{type(exc).__name__}: {exc}"},
        )


@app.post("/checkpoints/{thread_id}/decision")
async def submit_checkpoint_decision(thread_id: str, payload: ApprovalDecisionRequest):
    try:
        current_state = _get_thread_state(thread_id)
        if not current_state:
            return JSONResponse(status_code=404, content={"error": f"Geen checkpoint gevonden voor thread_id={thread_id}"})

        approved_indices = sorted(set(int(i) for i in payload.approved_indices))
        rejection_reasons_by_index = {
            int(k): v for k, v in payload.rejection_reasons_by_index.items()
        }

        # Merge existing state with human decision and resume workflow in same thread.
        updated_state = {
            **current_state,
            "thread_id": thread_id,
            "approval_order_indices": approved_indices,
            "rejection_reasons_by_index": rejection_reasons_by_index,
            "awaiting_human_approval": False,
            "approved_by": payload.approved_by,
            "approval_decision": payload.decision or ("approved" if approved_indices else "rejected"),
        }

        result = workflow.invoke(updated_state, config=_thread_config(thread_id))
        state = _safe_state(result)
        return JSONResponse(
            content={
                "thread_id": thread_id,
                "state": state,
                "pending": _is_pending_approval(state),
            }
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"{type(exc).__name__}: {exc}"},
        )
