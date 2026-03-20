from typing import Any, Dict, Optional
from pydantic import BaseModel

class ProcurementState(BaseModel):
    step: str = "daily_inventory_check"
    status: str = "pending"
    message: str = ""
    data: Dict[str, Any] = {}
    errors: list[str] = []

    # Checkpointing & human-in-the-loop fields
    thread_id: Optional[str] = None
    approval_requested_at: Optional[str] = None
    approval_decision: Optional[str] = None  # 'approved', 'rejected', 'pending'
    approval_reason: Optional[str] = None  # Human-provided reason for approval/rejection
    approved_by: Optional[str] = None
    approved_orders: list[int] = []
    rejection_reasons: Dict[int, str] = {}

    # Path selection fields for human-in-the-loop workflow choice
    awaiting_path_selection: bool = False
    path_choice: Optional[str] = None  # 'path_1_suppliers' or 'path_2_new_releases'

    # Approval interaction fields
    awaiting_human_approval: bool = False
    approval_order_indices: list[int] = []  # Indices of approved orders
    rejection_reasons_by_index: Dict[int, str] = {}  # Rejection reasons by order index

    # New release detection fields
    new_releases: list[Dict[str, Any]] = []
    existing_new_releases: list[Dict[str, Any]] = []
    new_releases_needing_stock: list[Dict[str, Any]] = []
    purchase_order_proposals: list[Dict[str, Any]] = []
    next_action: Optional[str] = None
    country: str = "US"  # Spotify API country code
    limit: int = 5  # Number of releases to fetch

    model_config = {
        "arbitrary_types_allowed": True
    }

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

