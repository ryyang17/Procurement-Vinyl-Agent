import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.utils.state import ProcurementState
from agent.utils.nodes.sales_nodes import analyse_sales_velocity_node
from agent.utils.nodes.inventory_nodes import daily_inventory_check_node


class TestVerkoopsnelheidReorder(unittest.TestCase):
    def test_hoge_verkoopsnelheid_triggert_earlier_reorder(self):
        """
        Use Case 6:
        Verify that a fast-selling product can trigger reorder using sales velocity
        even when stock is still above the static reorder level.
        """
        state = ProcurementState(
            step="analyse_sales_velocity",
            status="pending",
            message="",
            data={}
        )

        state = analyse_sales_velocity_node(state)

        self.assertIn('dynamic_reorder_levels', state.data)
        self.assertIn('sales_velocity_forecasts', state.data)

        dynamic_levels = state.data['dynamic_reorder_levels']
        self.assertIn('2', dynamic_levels, "Expected dynamic level for product_id 2 from dummy sales")
        self.assertGreater(dynamic_levels['2'], 20, "Dynamic threshold should exceed static reorder level")

        state = daily_inventory_check_node(state)

        proposals = state.data.get('reorder_proposals', [])
        product_2_proposal = next((p for p in proposals if p.get('product_id') == 2), None)

        self.assertIsNotNone(
            product_2_proposal,
            "Product 2 should be proposed for reorder due to high sales velocity"
        )
        self.assertEqual(
            product_2_proposal.get('reorder_basis'),
            'sales_velocity',
            "Proposal should be marked as sales_velocity-driven"
        )


if __name__ == '__main__':
    unittest.main()
