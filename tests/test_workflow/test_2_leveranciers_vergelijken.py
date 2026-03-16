import sys
from pathlib import Path
from unittest.mock import patch, Mock
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.utils.state import ProcurementState
from agent.utils.nodes.inventory_nodes import daily_inventory_check_node
from agent.utils.nodes.supplier_nodes import find_suppliers_node
from agent.procurement_data import ProcurementDatabase

class TestLeveranciersVergelijken(unittest.TestCase):
    def test_leveranciers_vergelijken(self):
        db = ProcurementDatabase()
        initial_state = ProcurementState(
            step="daily_inventory_check",
            status="pending",
            message="",
            data={}
        )
        inventory_state = daily_inventory_check_node(initial_state)
        if inventory_state.status != 'proposed':
            inventory_state.data['reorder_proposals'] = [{
                'product_code': 'VIN-001',
                'product_name': 'Test Vinyl',
                'current_qty': 5,
                'reorder_qty': 50,
                'min_threshold': 10
            }]
            inventory_state.status = 'proposed'
        with patch('agent.utils.nodes.supplier_nodes.ChatGoogleGenerativeAI') as mock_llm:
            mock_response = Mock()
            mock_response.content = "LEVERANCIER: Vinyl Distributors BV\nREDEN: Best price and quality combination"
            mock_llm.return_value.invoke.return_value = mock_response
            result_state = find_suppliers_node(inventory_state)
        self.assertIn('supplier_selections', result_state.data, "Supplier selections should exist")
        selections = result_state.data['supplier_selections']
        self.assertGreater(len(selections), 0, "Should have supplier selections")
        for selection in selections:
            self.assertIn('product_code', selection)
            self.assertIn('product_name', selection)
            self.assertIn('selected_supplier', selection)
            self.assertIn('all_options', selection)
            supplier = selection['selected_supplier']
            self.assertIn('supplier_id', supplier)
            self.assertIn('supplier_name', supplier)
            self.assertIn('price_per_unit', supplier)
            self.assertIn('lead_time_days', supplier)
            self.assertIn('quality_rating', supplier)
            options = selection['all_options']
            self.assertGreater(len(options), 0, "Should have supplier options to compare")

if __name__ == '__main__':
    unittest.main()
