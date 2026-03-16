import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.procurement_data import ProcurementDatabase

class TestOrderPlaatsenVoorraadBijwerken(unittest.TestCase):
    def test_order_plaatsen_voorraad_bijwerken(self):
        db = ProcurementDatabase()
        products = db.get_products()
        inventory = db.get_inventory()
        test_product = products[0]
        test_inventory = next(
            (i for i in inventory if i['product_id'] == test_product['product_id']),
            None
        )
        self.assertIsNotNone(test_inventory, "Product should have inventory entry")
        initial_stock = test_inventory['quantity_in_stock']
        suppliers = db.get_suppliers_for_product(test_product['product_id'])
        order_quantity = 100
        created_order = db.create_purchase_order(
            supplier_id=suppliers[0]['supplier_id'],
            items=[{
                'product_id': test_product['product_id'],
                'quantity': order_quantity,
                'unit_price': suppliers[0]['price_per_unit']
            }],
            approved_by='test_manager'
        )
        self.assertIsNotNone(created_order, "Order should be created")
        self.assertEqual(created_order['status'], 'approved', "Order should be approved")
        from datetime import datetime, timedelta
        orders = db.get_purchase_orders()
        for order in orders:
            if order['purchase_order_id'] == created_order['purchase_order_id']:
                past_date = datetime.now() - timedelta(days=1)
                order['expected_delivery_date'] = past_date.isoformat()
                break
        db.save_json('purchase_order.json', orders)
        processed_deliveries = db.process_due_deliveries()
        self.assertGreater(len(processed_deliveries), 0, "Should have processed deliveries")
        our_delivery = next(
            (d for d in processed_deliveries
             if d['order_id'] == created_order['purchase_order_id']),
            None
        )
        self.assertIsNotNone(our_delivery, "Our order should be in processed deliveries")
        updated_inventory = db.get_inventory()
        updated_test_inventory = next(
            (i for i in updated_inventory if i['product_id'] == test_product['product_id']),
            None
        )
        self.assertIsNotNone(updated_test_inventory, "Inventory should still exist")
        final_stock = updated_test_inventory['quantity_in_stock']
        self.assertEqual(final_stock, initial_stock + order_quantity, f"Stock should increase by {order_quantity}")
        final_orders = db.get_purchase_orders()
        final_order = next(
            (o for o in final_orders if o['purchase_order_id'] == created_order['purchase_order_id']),
            None
        )
        self.assertEqual(final_order['status'], 'delivered', "Order should be marked as delivered")

if __name__ == '__main__':
    unittest.main()
