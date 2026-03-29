from typing import Any, Dict, Optional, List
from pydantic import BaseModel

class ProcurementState(BaseModel):
    # Core workflow state
    step: str = "process_due_deliveries"
    status: str = "pending"
    message: str = ""
    data: Dict[str, Any] = {}
    errors: List[str] = []
    summary: Optional[str] = None
    current_date: Optional[str] = None

    # Checkpointing & thread management
    thread_id: Optional[str] = None
    approval_requested_at: Optional[str] = None
    approval_decision: Optional[str] = None  # 'approved', 'rejected', 'pending'
    approval_reason: Optional[str] = None
    approved_by: Optional[str] = None

    # Legacy approval fields (for backwards compatibility)
    approved_orders: List[int] = []
    rejection_reasons: Dict[int, str] = {}

    # Path selection fields for human-in-the-loop workflow choice
    awaiting_path_selection: bool = False
    path_choice: Optional[str] = None  # 'path_1_suppliers' or 'path_2_new_releases'

    # Modern approval interaction fields
    awaiting_human_approval: bool = False
    approval_order_indices: List[int] = []  # Indices of approved orders
    rejection_reasons_by_index: Dict[int, str] = {}  # Rejection reasons by order index

    # New release detection fields
    new_releases: List[Dict[str, Any]] = []
    existing_new_releases: List[Dict[str, Any]] = []
    new_releases_needing_stock: List[Dict[str, Any]] = []
    purchase_order_proposals: List[Dict[str, Any]] = []
    market_popular_albums: List[Dict[str, Any]] = []
    uncatalogued_popular_albums: List[Dict[str, Any]] = []
    next_action: Optional[str] = None

    # Spotify API configuration
    country: str = "US"
    limit: int = 5

    # UI helper fields (populated by nodes for frontend display)
    inventory_alerts: List[str] = []
    sales_velocity_alerts: List[str] = []
    new_release_alerts: List[str] = []
    market_popularity_alerts: List[str] = []
    supplier_offers: List[Dict[str, Any]] = []
    draft_orders: List[Dict[str, Any]] = []
    approved_orders_list: List[Dict[str, Any]] = []

    model_config = {
        "arbitrary_types_allowed": True
    }

    def add_supplier_order(self, order: Dict[str, Any]):
        """Add an order from supplier path, ensuring proper source tracking."""
        order_with_source = {
            **order,
            "source_type": order.get("source_type", "inventory_low_stock"),
            "order_path": order.get("order_path", "suppliers"),
        }
        if "draft_orders" not in self.data:
            self.data["draft_orders"] = []
        self.data["draft_orders"].append(order_with_source)

    def add_new_release_order(self, order: Dict[str, Any]):
        """Add an order from new release path, ensuring proper source tracking."""
        order_with_source = {
            **order,
            "source_type": order.get("source_type", "new_release_spotify"),
            "order_path": order.get("order_path", "new_releases"),
        }
        if "draft_orders" not in self.data:
            self.data["draft_orders"] = []
        self.data["draft_orders"].append(order_with_source)

    def get_supplier_orders(self) -> List[Dict[str, Any]]:
        """Get only orders from supplier path."""
        all_orders = self.data.get("draft_orders", [])
        return [order for order in all_orders if order.get("order_path") == "suppliers"]

    def get_new_release_orders(self) -> List[Dict[str, Any]]:
        """Get only orders from new release path."""
        all_orders = self.data.get("draft_orders", [])
        return [order for order in all_orders if order.get("order_path") == "new_releases"]

    def clear_path_data(self, path: str):
        """Clear data for a specific path to prevent cross-contamination."""
        if path == "suppliers":
            # Clear supplier-specific data
            self.data["reorder_proposals"] = []
            self.data["supplier_selections"] = []
            # Remove supplier orders
            current_orders = self.data.get("draft_orders", [])
            self.data["draft_orders"] = [o for o in current_orders if o.get("order_path") != "suppliers"]

        elif path == "new_releases":
            # Clear new release-specific data
            self.new_releases = []
            self.existing_new_releases = []
            self.new_releases_needing_stock = []
            self.purchase_order_proposals = []
            self.market_popular_albums = []
            self.uncatalogued_popular_albums = []
            self.market_popularity_alerts = []
            # Remove new release orders
            current_orders = self.data.get("draft_orders", [])
            self.data["draft_orders"] = [o for o in current_orders if o.get("order_path") != "new_releases"]

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

