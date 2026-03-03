"""
Order Operations - Purchase orders and invoice management
"""
from typing import Dict, List, Any
from datetime import datetime


class OrderOperations:
    """Handles all purchase order and invoice operations"""

    def __init__(self, db_connection):
        """Initialize with database connection"""
        self.conn = db_connection

    # ==================== PURCHASE ORDER OPERATIONS ====================

    def create_purchase_order(self, supplier_id: int, product_code: str,
                            quantity: int, unit_price: float,
                            expected_delivery_date: datetime = None,
                            llm_analysis: str = None) -> Dict[str, Any]:
        """
        R6: Create purchase order (pending approval)
        """
        cursor = self.conn.cursor()

        # Generate order number
        order_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{cursor.lastrowid or 1:04d}"
        total_cost = quantity * unit_price

        cursor.execute("""
            INSERT INTO purchase_orders 
            (order_number, supplier_id, product_code, quantity, unit_price, 
             total_cost, expected_delivery_date, llm_analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_number, supplier_id, product_code, quantity, unit_price,
              total_cost, expected_delivery_date, llm_analysis))

        self.conn.commit()

        return {
            'order_id': cursor.lastrowid,
            'order_number': order_number,
            'total_cost': total_cost
        }

    def approve_purchase_order(self, order_id: int, approved_by: str):
        """R8: Approve purchase order"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE purchase_orders 
            SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
            WHERE order_id = ?
        """, (approved_by, order_id))
        self.conn.commit()

    def reject_purchase_order(self, order_id: int, rejected_by: str):
        """R8: Reject purchase order"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE purchase_orders 
            SET status = 'rejected', approved_by = ?
            WHERE order_id = ?
        """, (rejected_by, order_id))
        self.conn.commit()

    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending purchase orders"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT po.*, s.supplier_name, p.product_name
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.supplier_id
            JOIN products p ON po.product_code = p.product_code
            WHERE po.status = 'pending'
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_order_by_id(self, order_id: int) -> Dict[str, Any]:
        """Get order details by ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT po.*, s.supplier_name, p.product_name
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.supplier_id
            JOIN products p ON po.product_code = p.product_code
            WHERE po.order_id = ?
        """, (order_id,))
        result = cursor.fetchone()
        return dict(result) if result else None

    def get_all_orders(self, status: str = None) -> List[Dict[str, Any]]:
        """Get all orders, optionally filtered by status"""
        cursor = self.conn.cursor()

        if status:
            cursor.execute("""
                SELECT po.*, s.supplier_name, p.product_name
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.supplier_id
                JOIN products p ON po.product_code = p.product_code
                WHERE po.status = ?
                ORDER BY po.created_at DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT po.*, s.supplier_name, p.product_name
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.supplier_id
                JOIN products p ON po.product_code = p.product_code
                ORDER BY po.created_at DESC
            """)

        return [dict(row) for row in cursor.fetchall()]

    # ==================== INVOICE OPERATIONS ====================

    def create_invoice(self, invoice_number: str, order_id: int, supplier_id: int,
                      invoice_amount: float, invoice_quantity: int) -> Dict[str, Any]:
        """
        R9-R10: Create invoice and detect discrepancies
        """
        cursor = self.conn.cursor()

        # Get original order details
        cursor.execute("""
            SELECT quantity, total_cost FROM purchase_orders WHERE order_id = ?
        """, (order_id,))
        order = cursor.fetchone()

        if not order:
            return {'error': 'Order not found'}

        discrepancy_type = None
        discrepancy_message = None

        # Check for discrepancies
        if invoice_quantity != order['quantity']:
            discrepancy_type = 'quantity'
            discrepancy_message = f"Quantity mismatch: Ordered {order['quantity']}, Invoiced {invoice_quantity}"

        if abs(invoice_amount - order['total_cost']) > 0.01:
            if discrepancy_type:
                discrepancy_type = 'both'
                discrepancy_message += f" | Price mismatch: Expected €{order['total_cost']:.2f}, Invoiced €{invoice_amount:.2f}"
            else:
                discrepancy_type = 'price'
                discrepancy_message = f"Price mismatch: Expected €{order['total_cost']:.2f}, Invoiced €{invoice_amount:.2f}"

        cursor.execute("""
            INSERT INTO invoices 
            (invoice_number, order_id, supplier_id, invoice_amount, invoice_quantity,
             discrepancy_type, discrepancy_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (invoice_number, order_id, supplier_id, invoice_amount, invoice_quantity,
              discrepancy_type, discrepancy_message))

        self.conn.commit()

        return {
            'invoice_id': cursor.lastrowid,
            'discrepancy_type': discrepancy_type,
            'discrepancy_message': discrepancy_message
        }

    def get_pending_invoice_verification(self) -> List[Dict[str, Any]]:
        """Get invoices with discrepancies"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM invoices 
            WHERE discrepancy_type IS NOT NULL AND status = 'pending'
        """)
        return [dict(row) for row in cursor.fetchall()]

    def approve_invoice(self, invoice_id: int):
        """Approve invoice (accept discrepancy or no discrepancy)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE invoices 
            SET status = 'approved'
            WHERE invoice_id = ?
        """, (invoice_id,))
        self.conn.commit()

    def reject_invoice(self, invoice_id: int):
        """Reject invoice due to discrepancies"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE invoices 
            SET status = 'rejected'
            WHERE invoice_id = ?
        """, (invoice_id,))
        self.conn.commit()

