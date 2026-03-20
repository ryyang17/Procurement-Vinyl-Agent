import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

class ProcurementDatabase:
    """Database helper class for managing procurement data from JSON files"""

    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), '../db')

    def load_json(self, filename: str) -> List[Dict[str, Any]]:
        """Load data from JSON file"""
        file_path = os.path.join(self.db_path, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_json(self, filename: str, data: List[Dict[str, Any]]) -> None:
        """Save data to JSON file"""
        file_path = os.path.join(self.db_path, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_inventory(self) -> List[Dict[str, Any]]:
        """Get all inventory items"""
        return self.load_json('inventory.json')

    def get_products(self) -> List[Dict[str, Any]]:
        """Get all products"""
        return self.load_json('product.json')

    def get_suppliers(self) -> List[Dict[str, Any]]:
        """Get all suppliers"""
        data = self.load_json('supplier.json')
        # Handle both list and dict with 'suppliers' key
        if isinstance(data, dict) and 'suppliers' in data:
            return data['suppliers']
        return data

    def get_supplier_performance(self) -> List[Dict[str, Any]]:
        """Get supplier performance data"""
        return self.load_json('supplier_performance.json')

    def get_price_history(self) -> List[Dict[str, Any]]:
        """Get price history"""
        return self.load_json('price_history.json')

    def get_purchase_orders(self) -> List[Dict[str, Any]]:
        """Get all purchase orders"""
        return self.load_json('purchase_order.json')

    def get_purchase_order_items(self) -> List[Dict[str, Any]]:
        """Get all purchase order items"""
        return self.load_json('purchase_order_item.json')

    def get_suppliers_for_product(self, product_id: int) -> List[Dict[str, Any]]:
        """Get all suppliers that can supply a specific product"""
        import random

        suppliers = self.get_suppliers()
        performance = self.get_supplier_performance()
        products = self.get_products()

        # Get base price for product
        product = next((p for p in products if p['product_id'] == product_id), None)
        if not product:
            return []

        base_price = product.get('current_price', 30.0)

        # For demo purposes, assume all suppliers can supply all products
        # In production, you'd have a supplier_products junction table
        options = []

        # Randomly select 3-5 suppliers for this product
        available_suppliers = random.sample(suppliers, min(3, len(suppliers)))

        for supplier in available_suppliers:
            # Get performance data
            perf = next((p for p in performance if p['supplier_id'] == supplier['supplier_id']), None)

            # Generate price variation (base price +/- 20%)
            price_variation = random.uniform(0.85, 1.15)
            price_per_unit = round(base_price * price_variation, 2)

            # Get or default lead time
            lead_time = supplier.get('lead_time_days', random.randint(3, 14))

            options.append({
                'supplier_id': supplier['supplier_id'],
                'supplier_name': supplier['name'],
                'price_per_unit': price_per_unit,
                'lead_time_days': lead_time,
                'late_deliveries_count': perf.get('late_deliveries', random.randint(0, 5)) if perf else random.randint(0, 5),
                'quality_rating': perf.get('reliability_score', round(random.uniform(0.6, 0.95), 2)) * 10 if perf else round(random.uniform(6.0, 9.5), 1)
            })

        return options

    def get_followed_artists(self) -> List[Dict[str, Any]]:
        """Get list of artists followed for new releases"""
        # In a real app, this would come from a database table or be derived from inventory
        # Returning a few sample artists with their Discogs IDs for the demo
        return [
            {"id": 82730, "name": "The Beatles"},
            {"id": 45467, "name": "Pink Floyd"},
            {"id": 3840, "name": "Radiohead"},
            {"id": 12345, "name": "The Solar Flares"}, # Fictional
        ]

    def create_purchase_order(self, supplier_id: int, items: List[Dict[str, Any]],
                            approved_by: Optional[str] = None) -> Dict[str, Any]:
        """Create a new purchase order"""
        orders = self.get_purchase_orders()
        order_items = self.get_purchase_order_items()

        # Generate new order ID - gebruik purchase_order_id zoals in JSON
        new_order_id = max([o['purchase_order_id'] for o in orders], default=0) + 1

        # Calculate total
        total_amount = sum(item['quantity'] * item['unit_price'] for item in items)

        # Calculate expected delivery date based on supplier performance
        expected_delivery_date = self._calculate_expected_delivery_date(supplier_id)

        # Create order
        new_order = {
            'purchase_order_id': new_order_id,
            'supplier_id': supplier_id,
            'order_date': datetime.now().isoformat(),
            'expected_delivery_date': expected_delivery_date,
            'status': 'approved' if approved_by else 'pending',
            'total_amount': total_amount,
            'approved_by': approved_by
        }

        # Create order items
        item_id_start = max([i['purchase_order_item_id'] for i in order_items], default=0) + 1
        for idx, item in enumerate(items):
            order_items.append({
                'purchase_order_item_id': item_id_start + idx,
                'purchase_order_id': new_order_id,
                'product_id': item['product_id'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price']
            })

        # Save
        orders.append(new_order)
        self.save_json('purchase_order.json', orders)
        self.save_json('purchase_order_item.json', order_items)

        return new_order

    def update_purchase_order_status(self, order_id: int, status: str, approved_by: Optional[str] = None) -> None:
        """Update purchase order status"""
        orders = self.get_purchase_orders()
        for order in orders:
            if order['purchase_order_id'] == order_id:
                order['status'] = status
                if approved_by:
                    order['approved_by'] = approved_by
                break
        self.save_json('purchase_order.json', orders)

    def get_pending_purchase_orders(self) -> List[Dict[str, Any]]:
        """Get all pending purchase orders with their items"""
        orders = self.get_purchase_orders()
        order_items = self.get_purchase_order_items()
        products = self.get_products()
        suppliers = self.get_suppliers()

        pending_orders = []

        for order in orders:
            if order.get('status', '').lower() == 'pending':
                # Get items for this order
                items = [item for item in order_items if item['purchase_order_id'] == order['purchase_order_id']]

                # Enrich items with product info
                enriched_items = []
                for item in items:
                    product = next((p for p in products if p['product_id'] == item['product_id']), None)
                    enriched_items.append({
                        'product_id': item['product_id'],
                        'product_name': product.get('name', 'Unknown') if product else 'Unknown',
                        'quantity': item['quantity'],
                        'unit_price': item['unit_price'],
                        'subtotal': item['quantity'] * item['unit_price']
                    })

                # Get supplier info
                supplier = next((s for s in suppliers if s['supplier_id'] == order['supplier_id']), None)

                pending_orders.append({
                    'purchase_order_id': order['purchase_order_id'],
                    'supplier_id': order['supplier_id'],
                    'supplier_name': supplier.get('name', 'Unknown') if supplier else 'Unknown',
                    'order_date': order.get('order_date'),
                    'expected_delivery_date': order.get('expected_delivery_date'),
                    'status': order.get('status'),
                    'total_amount': order.get('total_amount'),
                    'items': enriched_items
                })

        return pending_orders

    def get_order_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get latest purchase orders from DB enriched with supplier names."""
        orders = self.get_purchase_orders()
        suppliers = self.get_suppliers()

        supplier_map = {s.get('supplier_id'): s.get('name', 'Unknown') for s in suppliers}

        sorted_orders = sorted(
            orders,
            key=lambda o: o.get('order_date') or '',
            reverse=True,
        )

        history = []
        for order in sorted_orders[:limit]:
            history.append({
                'order_id': order.get('purchase_order_id'),
                'supplier_id': order.get('supplier_id'),
                'supplier_name': supplier_map.get(order.get('supplier_id'), 'Unknown'),
                'status': order.get('status'),
                'order_date': order.get('order_date'),
                'expected_delivery_date': order.get('expected_delivery_date'),
                'delivery_date': order.get('delivery_date'),
                'total_amount': order.get('total_amount'),
                'approved_by': order.get('approved_by'),
            })

        return history

    def _calculate_expected_delivery_date(self, supplier_id: int) -> str:
        """Calculate expected delivery date based on supplier lead time"""
        from datetime import timedelta

        suppliers = self.get_suppliers()

        # Get supplier info
        supplier = next((s for s in suppliers if s['supplier_id'] == supplier_id), None)
        if not supplier:
            # Default fallback: 7 days
            delivery_date = datetime.now() + timedelta(days=7)
            return delivery_date.isoformat()

        base_lead_time = supplier.get('lead_time_days', 7)

        # Calculate delivery date based on lead time
        delivery_date = datetime.now() + timedelta(days=base_lead_time)
        return delivery_date.isoformat()

    def process_due_deliveries(self) -> List[Dict[str, Any]]:
        """Process deliveries that are due today and update inventory accordingly"""
        orders = self.get_purchase_orders()
        order_items = self.get_purchase_order_items()
        products = self.get_products()
        suppliers = self.get_suppliers()
        inventory = self.get_inventory()

        processed_deliveries = []
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for order in orders:
            # Only process approved orders
            if order.get("status") != "approved":
                continue

            expected_date_str = order.get("expected_delivery_date")
            if not expected_date_str:
                continue

            try:
                expected_date = datetime.fromisoformat(expected_date_str.replace("Z", "+00:00"))
                expected_date = expected_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

                # Check if delivery is due (expected date is today or in the past)
                if expected_date <= current_date:
                    # Mark order as delivered
                    order['status'] = 'delivered'
                    delivery_date = datetime.now().isoformat()
                    order['delivery_date'] = delivery_date

                    # Get items for this order
                    items = [item for item in order_items if item.get("purchase_order_id") == order["purchase_order_id"]]

                    # Update inventory with delivered items
                    updated_products = []
                    for item in items:
                        # Safely check if quantity and product_id exist
                        if "quantity" not in item or "product_id" not in item:
                            continue

                        product = next((p for p in products if p.get("product_id") == item["product_id"]), None)
                        inv_item = next((i for i in inventory if i.get("product_id") == item["product_id"]), None)

                        if product and inv_item:
                            old_quantity = inv_item.get("quantity_in_stock", 0)
                            inv_item["quantity_in_stock"] = old_quantity + item["quantity"]
                            inv_item["last_updated"] = delivery_date

                            updated_products.append({
                                "product_id": item["product_id"],
                                "product_name": product.get("name", "Unknown"),
                                "quantity_added": item["quantity"],
                                "old_quantity": old_quantity,
                                "new_quantity": inv_item["quantity_in_stock"]
                            })

                    supplier = next((s for s in suppliers if s.get("supplier_id") == order["supplier_id"]), None)

                    # Add to processed deliveries (with or without items)
                    processed_deliveries.append({
                        "order_id": order["purchase_order_id"],
                        "supplier_name": supplier.get("name", "Unknown") if supplier else "Unknown",
                        "delivery_date": delivery_date,
                        "updated_products": updated_products
                    })

            except (ValueError, TypeError) as e:
                continue

        # Save updated data
        if processed_deliveries:
            self.save_json('purchase_order.json', orders)
            self.save_json('inventory.json', inventory)

        return processed_deliveries

    def get_low_stock_products(self) -> List[Dict[str, Any]]:
        """Get products that are at or below reorder level"""
        inventory = self.get_inventory()
        products = self.get_products()

        low_stock_items = []

        for inv_item in inventory:
            quantity = inv_item.get('quantity_in_stock', 0)
            reorder_level = inv_item.get('reorder_level', 0)

            if quantity <= reorder_level:
                # Find matching product
                product = next((p for p in products if p['product_id'] == inv_item['product_id']), None)

                if product:
                    low_stock_items.append({
                        'product_id': inv_item['product_id'],
                        'product_name': product['name'],
                        'sku': product.get('sku', 'N/A'),
                        'category': product.get('category', 'Unknown'),
                        'current_stock': quantity,
                        'reorder_level': reorder_level,
                        'shortage': max(0, reorder_level - quantity),
                        'current_price': product.get('current_price', 0),
                        'last_updated': inv_item.get('last_updated')
                    })

        return low_stock_items

    def detect_new_releases(self) -> List[Dict[str, Any]]:
        """Detect products that might be new releases based on creation date"""
        from datetime import timedelta

        products = self.get_products()
        inventory = self.get_inventory()

        # Consider products created in the last 7 days as "new releases"
        cutoff_date = datetime.now() - timedelta(days=7)

        new_releases = []

        for product in products:
            created_at_str = product.get('created_at')
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00').replace('+00:00', ''))

                    if created_at >= cutoff_date:
                        # Get inventory info
                        inv_item = next((i for i in inventory if i['product_id'] == product['product_id']), None)

                        stock_info = {
                            'current_stock': 0,
                            'reorder_level': 20,
                            'needs_reorder': True
                        }

                        if inv_item:
                            stock_info.update({
                                'current_stock': inv_item.get('quantity_in_stock', 0),
                                'reorder_level': inv_item.get('reorder_level', 20),
                                'needs_reorder': inv_item.get('quantity_in_stock', 0) <= inv_item.get('reorder_level', 20)
                            })

                        new_releases.append({
                            'product_id': product['product_id'],
                            'name': product['name'],
                            'sku': product.get('sku', 'N/A'),
                            'category': product.get('category', 'Unknown'),
                            'created_at': created_at_str,
                            'current_price': product.get('current_price', 0),
                            'artist': product.get('artist', 'Unknown'),
                            'discogs_id': product.get('discogs_id'),
                            **stock_info
                        })

                except (ValueError, TypeError):
                    continue

        return new_releases



    def product_exists(self, product_id):
        """Check if a product exists in the catalog by product_id."""
        products = self.get_products()
        return any(p.get('product_id') == product_id or p.get('id') == product_id for p in products)

    def add_product(self, product_data):
        """Add a new product to the catalog."""
        products = self.get_products()
        # Determine new product_id
        new_product_id = max([p.get('product_id', 0) for p in products], default=0) + 1
        product_data['product_id'] = new_product_id
        product_data['created_at'] = product_data.get('created_at', datetime.now().isoformat())
        products.append(product_data)
        self.save_json('product.json', products)
        return product_data

    def add_inventory(self, inventory_data):
        """Add a new inventory entry for a product."""
        inventory = self.get_inventory()
        # Determine new inventory_id
        new_inventory_id = max([i.get('inventory_id', 0) for i in inventory], default=0) + 1
        inventory_data['inventory_id'] = new_inventory_id
        inventory_data['last_updated'] = inventory_data.get('last_updated', datetime.now().isoformat())
        inventory.append(inventory_data)
        self.save_json('inventory.json', inventory)
        return inventory_data

