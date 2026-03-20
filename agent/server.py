from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agent.agent import create_procurement_workflow

app = FastAPI(title="Procurement Vinyl Agent API")
workflow = create_procurement_workflow()


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


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/predict")
async def predict(request: Request):
    try:
        payload = await request.json()
        input_state = payload.get("state", {}) if isinstance(payload, dict) else {}

        # LangGraph accepts plain dict input for most workflows
        result = workflow.invoke(input_state)

        return JSONResponse(content={"state": _safe_state(result)})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"{type(exc).__name__}: {exc}"},
        )
