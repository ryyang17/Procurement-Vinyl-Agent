import sys
from pathlib import Path
from unittest.mock import patch, Mock
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.utils.state import ProcurementState
from agent.utils.nodes.approval_nodes import human_approval_node, process_approval_node
from agent.procurement_data import ProcurementDatabase

class TestHumanApproval(unittest.TestCase):
    def test_human_approval(self):
        db = ProcurementDatabase()
        initial_state = ProcurementState(
            step="daily_inventory_check",
            status="pending",
            message="",
            data={}
        )
        products = db.get_products()
        test_product = products[0] if products else None
        suppliers = db.get_suppliers_for_product(test_product['product_id'])
        draft_order = {
            'supplier_id': suppliers[0]['supplier_id'],
            'supplier_name': suppliers[0]['supplier_name'],
            'items': [{
                'product_id': test_product['product_id'],
                'product_name': test_product['name'],
                'product_code': test_product.get('sku', 'TEST-001'),
                'quantity': 50,
                'unit_price': suppliers[0]['price_per_unit']
            }],
            'total_amount': 50 * suppliers[0]['price_per_unit'],
            'ai_recommendation': 'Best supplier',
            'lead_time_days': suppliers[0]['lead_time_days'],
            'quality_rating': suppliers[0]['quality_rating']
        }
        state_with_draft = initial_state
        state_with_draft.data['draft_orders'] = [draft_order]
        result_state = human_approval_node(state_with_draft)
        self.assertEqual(result_state.step, 'awaiting_human_input', "Should be awaiting human input")
        self.assertEqual(result_state.status, 'awaiting_approval', "Status should be awaiting approval")
        self.assertIsNotNone(result_state.approval_requested_at, "Approval timestamp should be set")
        approved_orders = [0]  # Approve first order
        approval_state = process_approval_node(
            result_state,
            approved_orders=approved_orders,
            approved_by="test_manager"
        )
        self.assertEqual(approval_state.status, 'orders_placed', "Status should be orders_placed after approval")
        self.assertIn('created_orders', approval_state.data, "Created orders should exist")
        self.assertEqual(len(approval_state.data['created_orders']), len(approved_orders), "Number of created orders should match approved orders")
        orders = db.get_purchase_orders()
        latest_order = max(orders, key=lambda x: x['purchase_order_id'])
        self.assertEqual(latest_order['status'], 'approved', "Order should be approved")
        self.assertEqual(latest_order['approved_by'], 'test_manager', "Order should record who approved it")

if __name__ == '__main__':
    unittest.main()
