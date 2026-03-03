"""
Supplier Operations - Supplier management and performance tracking
"""
from typing import Dict, List, Any


class SupplierOperations:
    """Handles all supplier-related database operations"""

    def __init__(self, db_connection):
        """Initialize with database connection"""
        self.conn = db_connection

    def find_suppliers_for_product(self, product_code: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        R4: Find suppliers for a product (max 3)
        Returns suppliers sorted by price
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT 
                s.supplier_id,
                s.supplier_name,
                s.avg_lead_time_days,
                s.quality_rating,
                s.late_deliveries_count,
                sp.price_per_unit,
                sp.min_order_qty,
                sp.packaging_unit
            FROM suppliers s
            JOIN supplier_products sp ON s.supplier_id = sp.supplier_id
            WHERE sp.product_code = ?
            ORDER BY sp.price_per_unit ASC
            LIMIT ?
        """, (product_code, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_all_suppliers(self) -> List[Dict[str, Any]]:
        """Get all suppliers"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM suppliers")
        return [dict(row) for row in cursor.fetchall()]

    def get_supplier_by_id(self, supplier_id: int) -> Dict[str, Any]:
        """Get supplier details by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,))
        result = cursor.fetchone()
        return dict(result) if result else None

    def update_supplier_late_delivery(self, supplier_id: int):
        """
        R11: Track late deliveries
        Increments the late delivery counter for a supplier
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE suppliers 
            SET late_deliveries_count = late_deliveries_count + 1
            WHERE supplier_id = ?
        """, (supplier_id,))
        self.conn.commit()

    def update_supplier_last_price(self, supplier_id: int, price: float):
        """
        R11: Track last price paid
        Updates the price for all products from this supplier
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE supplier_products 
            SET price_per_unit = ?, last_price_update = CURRENT_TIMESTAMP
            WHERE supplier_id = ?
        """, (price, supplier_id))
        self.conn.commit()

    def get_supplier_performance(self, supplier_id: int) -> Dict[str, Any]:
        """
        Get supplier performance metrics
        Returns quality rating, late deliveries, and total orders
        """
        cursor = self.conn.cursor()

        # Get supplier info
        cursor.execute("""
            SELECT 
                supplier_name,
                quality_rating,
                late_deliveries_count,
                avg_lead_time_days
            FROM suppliers
            WHERE supplier_id = ?
        """, (supplier_id,))
        supplier = cursor.fetchone()

        if not supplier:
            return {'error': 'Supplier not found'}

        # Get total orders from this supplier
        cursor.execute("""
            SELECT COUNT(*) as total_orders,
                   SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_orders
            FROM purchase_orders
            WHERE supplier_id = ?
        """, (supplier_id,))
        orders = cursor.fetchone()

        return {
            'supplier_name': supplier['supplier_name'],
            'quality_rating': supplier['quality_rating'],
            'late_deliveries': supplier['late_deliveries_count'],
            'avg_lead_time_days': supplier['avg_lead_time_days'],
            'total_orders': orders['total_orders'],
            'approved_orders': orders['approved_orders']
        }

