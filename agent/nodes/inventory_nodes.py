from agent.models import ProcurementState
from agent.procurement_data import ProcurementDatabase

db = ProcurementDatabase()

def daily_inventory_check_node(state: ProcurementState) -> ProcurementState:
    """
    R1: Agent checks inventory daily with LLM intelligence
    R2: If stock under minimum, generate purchase proposal
    R3: Reorder quantity depends on current stock, sales velocity, and lead time
    """
    # ...existing code from nodes.py daily_inventory_check_node...
