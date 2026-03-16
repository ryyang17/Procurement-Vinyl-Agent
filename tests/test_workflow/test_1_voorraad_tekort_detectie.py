import sys
from pathlib import Path
from unittest.mock import Mock, patch
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.utils.state import ProcurementState
from agent.utils.nodes.inventory_nodes import daily_inventory_check_node
from agent.procurement_data import ProcurementDatabase


class TestVoorraadTekortDetectie(unittest.TestCase):
    def test_voorraad_tekort_detectie(self):
        """
        Test 1: Voorraadtekort detectie
        Verify that the system correctly identifies products below reorder level
        """
        db = ProcurementDatabase()
        initial_state = ProcurementState(
            step="daily_inventory_check",
            status="pending",
            message="",
            data={}
        )
        result_state = daily_inventory_check_node(initial_state)
        self.assertIn(result_state.status, ['proposed', 'ok'], "Status should be 'proposed' or 'ok'")
        if result_state.status == 'proposed':
            self.assertIn('reorder_proposals', result_state.data, "Reorder proposals should exist")
            proposals = result_state.data['reorder_proposals']
            self.assertGreater(len(proposals), 0, "Should have at least one reorder proposal")
            for proposal in proposals:
                self.assertIn('product_code', proposal)
                self.assertIn('product_name', proposal)
                self.assertIn('current_qty', proposal)
                self.assertIn('reorder_qty', proposal)
                self.assertIn('min_threshold', proposal)
                self.assertLessEqual(proposal['current_qty'], proposal['min_threshold'],
                    "Current quantity should be at or below minimum threshold")


if __name__ == '__main__':
    unittest.main()
