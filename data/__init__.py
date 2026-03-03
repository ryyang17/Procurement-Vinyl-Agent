"""
Procurement Database - Main interface combining all operations
This is the main entry point for all database operations
"""
from .base import DatabaseBase
from .inventory_ops import InventoryOperations
from .supplier_ops import SupplierOperations
from .order_ops import OrderOperations
from .memory_ops import MemoryOperations


class ProcurementDatabase(DatabaseBase):
    """
    Main database interface for procurement operations
    Combines all operation modules into a single unified interface
    """

    def __init__(self, db_path: str = "data/procurement.db"):
        """Initialize database and all operation modules"""
        super().__init__(db_path)

        # Initialize operation modules with the shared connection
        self._inventory_ops = InventoryOperations(self.conn)
        self._supplier_ops = SupplierOperations(self.conn)
        self._order_ops = OrderOperations(self.conn)
        self._memory_ops = MemoryOperations(self.conn)

    # ==================== INVENTORY OPERATIONS ====================

    def daily_inventory_check(self):
        """Check inventory with intelligent threshold calculation"""
        return self._inventory_ops.daily_inventory_check()

    def generate_reorder_proposal(self, product_code: str, reorder_qty: int,
                                  reasoning: str = None, llm_analysis: str = None):
        """Generate reorder proposal with LLM reasoning"""
        return self._inventory_ops.generate_reorder_proposal(
            product_code, reorder_qty, reasoning, llm_analysis
        )

    def update_sales_velocity(self, product_code: str, days: int = 30):
        """Calculate and update sales velocity from history"""
        return self._inventory_ops.update_sales_velocity(product_code, days)

    def add_sale(self, product_code: str, quantity: int, sale_date=None):
        """Record a sale for velocity tracking"""
        return self._inventory_ops.add_sale(product_code, quantity, sale_date)

    def get_inventory(self):
        """Get all inventory items"""
        return self._inventory_ops.get_inventory()

    # ==================== SUPPLIER OPERATIONS ====================

    def find_suppliers_for_product(self, product_code: str, limit: int = 3):
        """Find suppliers for a product (max 3)"""
        return self._supplier_ops.find_suppliers_for_product(product_code, limit)

    def get_all_suppliers(self):
        """Get all suppliers"""
        return self._supplier_ops.get_all_suppliers()

    def get_supplier_by_id(self, supplier_id: int):
        """Get supplier details by ID"""
        return self._supplier_ops.get_supplier_by_id(supplier_id)

    def update_supplier_late_delivery(self, supplier_id: int):
        """Track late deliveries for a supplier"""
        return self._supplier_ops.update_supplier_late_delivery(supplier_id)

    def update_supplier_last_price(self, supplier_id: int, price: float):
        """Update last price paid to supplier"""
        return self._supplier_ops.update_supplier_last_price(supplier_id, price)

    def get_supplier_performance(self, supplier_id: int):
        """Get supplier performance metrics"""
        return self._supplier_ops.get_supplier_performance(supplier_id)

    # ==================== ORDER OPERATIONS ====================

    def create_purchase_order(self, supplier_id: int, product_code: str,
                            quantity: int, unit_price: float,
                            expected_delivery_date=None, llm_analysis: str = None):
        """Create purchase order (pending approval)"""
        return self._order_ops.create_purchase_order(
            supplier_id, product_code, quantity, unit_price,
            expected_delivery_date, llm_analysis
        )

    def approve_purchase_order(self, order_id: int, approved_by: str):
        """Approve purchase order"""
        return self._order_ops.approve_purchase_order(order_id, approved_by)

    def reject_purchase_order(self, order_id: int, rejected_by: str):
        """Reject purchase order"""
        return self._order_ops.reject_purchase_order(order_id, rejected_by)

    def get_pending_orders(self):
        """Get all pending purchase orders"""
        return self._order_ops.get_pending_orders()

    def get_order_by_id(self, order_id: int):
        """Get order details by ID"""
        return self._order_ops.get_order_by_id(order_id)

    def get_all_orders(self, status: str = None):
        """Get all orders, optionally filtered by status"""
        return self._order_ops.get_all_orders(status)

    # ==================== INVOICE OPERATIONS ====================

    def create_invoice(self, invoice_number: str, order_id: int, supplier_id: int,
                      invoice_amount: float, invoice_quantity: int):
        """Create invoice and detect discrepancies"""
        return self._order_ops.create_invoice(
            invoice_number, order_id, supplier_id, invoice_amount, invoice_quantity
        )

    def get_pending_invoice_verification(self):
        """Get invoices with discrepancies"""
        return self._order_ops.get_pending_invoice_verification()

    def approve_invoice(self, invoice_id: int):
        """Approve invoice"""
        return self._order_ops.approve_invoice(invoice_id)

    def reject_invoice(self, invoice_id: int):
        """Reject invoice"""
        return self._order_ops.reject_invoice(invoice_id)

    # ==================== MEMORY OPERATIONS ====================

    def store_agent_memory(self, context_type: str, decision_context: str,
                          llm_reasoning: str, confidence_score: float = None,
                          product_code: str = None, supplier_id: int = None):
        """Store LLM reasoning and context"""
        return self._memory_ops.store_agent_memory(
            context_type, decision_context, llm_reasoning,
            confidence_score, product_code, supplier_id
        )

    def get_agent_memory(self, context_type: str = None, product_code: str = None,
                        supplier_id: int = None, limit: int = 10):
        """Retrieve relevant agent memory"""
        return self._memory_ops.get_agent_memory(
            context_type, product_code, supplier_id, limit
        )

    def get_memory_by_id(self, memory_id: int):
        """Get specific memory record by ID"""
        return self._memory_ops.get_memory_by_id(memory_id)

    def get_recent_decisions(self, limit: int = 20):
        """Get most recent AI decisions"""
        return self._memory_ops.get_recent_decisions(limit)

    def get_memory_stats(self):
        """Get statistics about stored memories"""
        return self._memory_ops.get_memory_stats()

    def delete_old_memories(self, days: int = 90):
        """Delete memories older than specified days"""
        return self._memory_ops.delete_old_memories(days)


# Expose the main class at package level
__all__ = ['ProcurementDatabase']

