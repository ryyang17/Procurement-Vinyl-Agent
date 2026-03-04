from typing import Any, Dict
from pydantic import BaseModel

class ProcurementState(BaseModel):
    """Main state model for the procurement workflow"""
    step: str = "daily_inventory_check"
    status: str = "pending"
    message: str = ""
    data: Dict[str, Any] = {}
    errors: list[str] = []

    class Config:
        arbitrary_types_allowed = True

class ReorderProposal(BaseModel):
    """Model for bijhouden van reorder voorstellen"""
    product_code: str
    product_name: str
    current_qty: int
    reorder_qty: int
    min_threshold: int

class SupplierOption(BaseModel):
    """Model voor leverancieropties"""
    supplier_id: int
    supplier_name: str
    product_code: str
    price_per_unit: float
    lead_time_days: int
    late_deliveries_count: int
    quality_rating: float

