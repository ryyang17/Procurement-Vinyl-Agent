import sys
from pathlib import Path
from unittest.mock import patch, Mock
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.utils.state import ProcurementState
from agent.utils.nodes.order_nodes import create_purchase_order_node
from agent.procurement_data import ProcurementDatabase

class TestConceptBestellingOpstellen(unittest.TestCase):
    def test_conceptbestelling_opstellen(self):
        db = ProcurementDatabase()
        initial_state = ProcurementState(
            step="daily_inventory_check",
            status="pending",
            message="",
            data={}
        )
        products = db.get_products()
        test_product = products[0] if products else None
        self.assertIsNotNone(test_product, "Need at least one product in database")
        suppliers_for_product = db.get_suppliers_for_product(test_product['product_id'])
        self.assertGreater(len(suppliers_for_product), 0, "Need at least one supplier")
        state_with_selections = initial_state
        state_with_selections.data['supplier_selections'] = [{
            'product_code': test_product.get('sku', 'TEST-001'),
            'product_name': test_product['name'],
            'product_id': test_product['product_id'],
            'reorder_qty': 100,
            'selected_supplier': suppliers_for_product[0],
            'all_options': suppliers_for_product,
            'ai_recommendation': 'Selected based on best price'
        }]
        with patch('agent.utils.nodes.order_nodes.ChatGoogleGenerativeAI') as mock_llm:
            mock_llm.return_value = Mock()
            result_state = create_purchase_order_node(state_with_selections)
        self.assertEqual(result_state.status, 'awaiting_approval', "Status should be awaiting approval")
        self.assertIn('draft_orders', result_state.data, "Draft orders should exist")
        draft_orders = result_state.data['draft_orders']
        self.assertGreater(len(draft_orders), 0, "Should have draft orders")
        for order in draft_orders:
            self.assertIn('supplier_id', order)
            self.assertIn('supplier_name', order)
            self.assertIn('items', order)
            self.assertIn('total_amount', order)
            self.assertGreater(len(order['items']), 0, "Order should have items")
            for item in order['items']:
                self.assertIn('product_id', item)
                self.assertIn('product_name', item)
                self.assertIn('quantity', item)
                self.assertIn('unit_price', item)
            calculated_total = sum(
                item['quantity'] * item['unit_price']
                for item in order['items']
            )
            self.assertAlmostEqual(order['total_amount'], calculated_total, places=2, msg="Total amount should match sum of items")

if __name__ == '__main__':
    unittest.main()
