from agent.models import ProcurementState
from agent.procurement_data import ProcurementDatabase

db = ProcurementDatabase()

def human_approval_node(state: ProcurementState, approved: bool = False, approved_by: str = "system") -> ProcurementState:
    """
    R6: Human must approve each order
    R7: Show supplier, quantity, total price
    R8: Order only placed after approval
    """
    # ...existing code from nodes.py human_approval_node...
