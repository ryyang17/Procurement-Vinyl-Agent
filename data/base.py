"""
Database Base Layer - Connection and Table Creation
"""
import sqlite3
from pathlib import Path


class DatabaseBase:
    """Base database handler with connection and schema management"""

    def __init__(self, db_path: str = "data/procurement_vinyl.db"):
        """Initialize database connection"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create all database tables if they don't exist"""
        cursor = self.conn.cursor()

        # Suppliers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                contact_email TEXT,
                avg_lead_time_days INTEGER DEFAULT 7,
                quality_rating REAL DEFAULT 4.0,
                late_deliveries_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Products catalog
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_code TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Inventory table with intelligent thresholds
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                product_code TEXT PRIMARY KEY,
                current_qty INTEGER NOT NULL DEFAULT 0,
                min_threshold INTEGER NOT NULL DEFAULT 10,
                max_capacity INTEGER NOT NULL DEFAULT 100,
                safety_stock INTEGER NOT NULL DEFAULT 5,
                avg_daily_sales REAL DEFAULT 2.0,
                sales_velocity_trend TEXT DEFAULT 'stable',
                last_reorder_date TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_code) REFERENCES products(product_code)
            )
        """)

        # Sales history for forecasting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_history (
                sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL,
                quantity_sold INTEGER NOT NULL,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_code) REFERENCES products(product_code)
            )
        """)

        # Supplier-Product pricing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supplier_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                product_code TEXT NOT NULL,
                price_per_unit REAL NOT NULL,
                min_order_qty INTEGER DEFAULT 1,
                packaging_unit INTEGER DEFAULT 1,
                last_price_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
                FOREIGN KEY (product_code) REFERENCES products(product_code)
            )
        """)

        # Purchase Orders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                supplier_id INTEGER NOT NULL,
                product_code TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_cost REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                expected_delivery_date TIMESTAMP,
                approved_by TEXT,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                llm_analysis TEXT,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
                FOREIGN KEY (product_code) REFERENCES products(product_code)
            )
        """)

        # Invoices
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                order_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL,
                invoice_amount REAL NOT NULL,
                invoice_quantity INTEGER NOT NULL,
                discrepancy_type TEXT,
                discrepancy_message TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES purchase_orders(order_id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
            )
        """)

        # Reorder Proposals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reorder_proposals (
                proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL,
                proposed_qty INTEGER NOT NULL,
                reason TEXT,
                forecasted_stockout_date TIMESTAMP,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                llm_reasoning TEXT,
                FOREIGN KEY (product_code) REFERENCES products(product_code)
            )
        """)

        # Agent Memory for LLM
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_type TEXT NOT NULL,
                product_code TEXT,
                supplier_id INTEGER,
                decision_context TEXT,
                llm_reasoning TEXT,
                confidence_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def close(self):
        """Close database connection"""
        self.conn.close()

