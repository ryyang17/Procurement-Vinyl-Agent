"""
Inventory Operations - Stock management and sales velocity tracking
"""
from typing import Dict, List, Any
from datetime import datetime, timedelta


class InventoryOperations:
    """Handles all inventory-related database operations"""

    def __init__(self, db_connection):
        """Initialize with database connection"""
        self.conn = db_connection

    def daily_inventory_check(self) -> Dict[str, Any]:
        """
        R1: Daily inventory check with intelligent threshold calculation
        Considers: sales velocity, lead time, safety margin
        """
        cursor = self.conn.cursor()

        # Get all inventory items with their sales metrics
        cursor.execute("""
            SELECT 
                i.product_code,
                p.product_name,
                i.current_qty,
                i.min_threshold,
                i.max_capacity,
                i.safety_stock,
                i.avg_daily_sales,
                i.sales_velocity_trend,
                MIN(sp.supplier_id) as default_supplier_id,
                AVG(s.avg_lead_time_days) as avg_lead_time
            FROM inventory i
            JOIN products p ON i.product_code = p.product_code
            LEFT JOIN supplier_products sp ON i.product_code = sp.product_code
            LEFT JOIN suppliers s ON sp.supplier_id = s.supplier_id
            GROUP BY i.product_code
        """)

        items = cursor.fetchall()
        items_below_threshold = []

        for item in items:
            product_code = item['product_code']
            current_qty = item['current_qty']
            avg_daily_sales = item['avg_daily_sales']
            lead_time = item['avg_lead_time'] or 7
            safety_stock = item['safety_stock']

            # Calculate intelligent reorder point
            # Formula: (avg_daily_sales * lead_time) + safety_stock
            calculated_reorder_point = (avg_daily_sales * lead_time) + safety_stock

            # Calculate expected stockout date
            if avg_daily_sales > 0:
                days_until_stockout = current_qty / avg_daily_sales
                expected_stockout_date = datetime.now() + timedelta(days=days_until_stockout)
            else:
                days_until_stockout = 999
                expected_stockout_date = None

            # Check if reorder is needed
            if current_qty <= calculated_reorder_point:
                items_below_threshold.append({
                    'product_code': product_code,
                    'product_name': item['product_name'],
                    'current_qty': current_qty,
                    'min_threshold': item['min_threshold'],
                    'calculated_reorder_point': int(calculated_reorder_point),
                    'max_capacity': item['max_capacity'],
                    'avg_daily_sales': avg_daily_sales,
                    'lead_time_days': lead_time,
                    'days_until_stockout': int(days_until_stockout),
                    'expected_stockout_date': expected_stockout_date,
                    'sales_trend': item['sales_velocity_trend']
                })

        return {
            'total_checked': len(items),
            'items_below_threshold': items_below_threshold,
            'check_timestamp': datetime.now().isoformat()
        }

    def generate_reorder_proposal(self, product_code: str, reorder_qty: int,
                                  reasoning: str = None, llm_analysis: str = None) -> Dict[str, Any]:
        """
        R2: Generate reorder proposal with LLM reasoning
        """
        cursor = self.conn.cursor()

        # Get inventory data for forecasting
        cursor.execute("""
            SELECT current_qty, avg_daily_sales, max_capacity
            FROM inventory WHERE product_code = ?
        """, (product_code,))
        inv = cursor.fetchone()

        if not inv:
            return {'error': 'Product not found'}

        # Calculate forecasted stockout date
        if inv['avg_daily_sales'] > 0:
            days_to_stockout = inv['current_qty'] / inv['avg_daily_sales']
            forecasted_stockout = datetime.now() + timedelta(days=days_to_stockout)
        else:
            forecasted_stockout = None

        reason = reasoning or f"Stock below reorder point. Current: {inv['current_qty']}, Target: {inv['max_capacity']}"

        cursor.execute("""
            INSERT INTO reorder_proposals 
            (product_code, proposed_qty, reason, forecasted_stockout_date, llm_reasoning)
            VALUES (?, ?, ?, ?, ?)
        """, (product_code, reorder_qty, reason, forecasted_stockout, llm_analysis))

        self.conn.commit()

        return {
            'proposal_id': cursor.lastrowid,
            'product_code': product_code,
            'proposed_qty': reorder_qty,
            'forecasted_stockout_date': forecasted_stockout
        }

    def update_sales_velocity(self, product_code: str, days: int = 30) -> Dict[str, Any]:
        """
        Calculate sales velocity from recent sales history
        Returns avg daily sales and trend (increasing/stable/decreasing)
        """
        cursor = self.conn.cursor()

        # Get sales for the period
        cursor.execute("""
            SELECT SUM(quantity_sold) as total_sold, COUNT(*) as sale_count
            FROM sales_history
            WHERE product_code = ? 
            AND sale_date >= datetime('now', '-' || ? || ' days')
        """, (product_code, days))

        result = cursor.fetchone()
        total_sold = result['total_sold'] or 0
        avg_daily_sales = total_sold / days if days > 0 else 0

        # Determine trend (compare last 15 days vs previous 15 days)
        cursor.execute("""
            SELECT SUM(quantity_sold) as recent_sold
            FROM sales_history
            WHERE product_code = ? 
            AND sale_date >= datetime('now', '-15 days')
        """, (product_code,))
        recent_sold = cursor.fetchone()['recent_sold'] or 0

        cursor.execute("""
            SELECT SUM(quantity_sold) as previous_sold
            FROM sales_history
            WHERE product_code = ? 
            AND sale_date BETWEEN datetime('now', '-30 days') AND datetime('now', '-15 days')
        """, (product_code,))
        previous_sold = cursor.fetchone()['previous_sold'] or 0

        # Determine trend
        if recent_sold > previous_sold * 1.2:
            trend = 'increasing'
        elif recent_sold < previous_sold * 0.8:
            trend = 'decreasing'
        else:
            trend = 'stable'

        # Update inventory table
        cursor.execute("""
            UPDATE inventory 
            SET avg_daily_sales = ?, sales_velocity_trend = ?, last_updated = CURRENT_TIMESTAMP
            WHERE product_code = ?
        """, (avg_daily_sales, trend, product_code))

        self.conn.commit()

        return {
            'product_code': product_code,
            'avg_daily_sales': avg_daily_sales,
            'trend': trend,
            'recent_sold': recent_sold,
            'previous_sold': previous_sold
        }

    def add_sale(self, product_code: str, quantity: int, sale_date: datetime = None):
        """Record a sale for velocity tracking"""
        cursor = self.conn.cursor()
        sale_date = sale_date or datetime.now()

        cursor.execute("""
            INSERT INTO sales_history (product_code, quantity_sold, sale_date)
            VALUES (?, ?, ?)
        """, (product_code, quantity, sale_date))

        # Update current inventory
        cursor.execute("""
            UPDATE inventory SET current_qty = current_qty - ?
            WHERE product_code = ?
        """, (quantity, product_code))

        self.conn.commit()

    def get_inventory(self) -> List[Dict[str, Any]]:
        """Get all inventory items"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT i.*, p.product_name 
            FROM inventory i
            JOIN products p ON i.product_code = p.product_code
        """)
        return [dict(row) for row in cursor.fetchall()]

