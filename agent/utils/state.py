from typing import Any, Dict, Optional
from pydantic import BaseModel

class ProcurementState(BaseModel):
    step: str = "daily_inventory_check"
    status: str = "pending"
    message: str = ""
    data: Dict[str, Any] = {}
    errors: list[str] = []

    # Checkpointing & human-in-the-loop fields
    thread_id: Optional[str] = None  # For workflow resumption across sessions
    approval_requested_at: Optional[str] = None
    approval_decision: Optional[str] = None  # 'approved', 'rejected', 'pending'
    approval_reason: Optional[str] = None  # Human-provided reason for approval/rejection
    approved_by: Optional[str] = None
    approved_orders: list[int] = []
    rejection_reasons: Dict[int, str] = {}

    """zorgt ervoor meer flexibiliteit in de types die in de data kunnen worden opgeslagen, zoals lists, dicts, of zelfs custom objects"""
    class Config:
        arbitrary_types_allowed = True

class ReorderProposal(BaseModel):
    product_code: str
    product_name: str
    current_qty: int
    reorder_qty: int
    min_threshold: int

class SupplierOption(BaseModel):
    supplier_id: int
    supplier_name: str
    product_code: str
    price_per_unit: float
    lead_time_days: int
    late_deliveries_count: int
    quality_rating: float

