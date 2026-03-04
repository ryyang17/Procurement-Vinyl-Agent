from agent.models import ProcurementState
from agent.procurement_data import ProcurementDatabase

db = ProcurementDatabase()

def human_approval_node(state: ProcurementState) -> ProcurementState:
    """
    R6: Human must approve each order
    R7: Show supplier, quantity, total price
    R8: Order only placed after approval

    This node requires human interaction - it will be handled by main.py
    """
    draft_orders = state.data.get('draft_orders', [])

    if not draft_orders:
        state.message = "Geen bestellingen om goed te keuren."
        state.step = "complete"
        return state

    # This state indicates we're waiting for human approval
    # The main.py will handle the interaction
    state.message = f"{len(draft_orders)} bestellingen wachten op goedkeuring."
    state.step = "awaiting_human_input"
    state.status = "awaiting_approval"

    return state

def process_approval_node(state: ProcurementState, approved_orders: list, approved_by: str = "manager") -> ProcurementState:
    """
    Process the human approval decisions and create actual purchase orders
    """
    if not approved_orders:
        state.message = "Geen bestellingen goedgekeurd."
        state.step = "complete"
        state.status = "cancelled"
        return state

    draft_orders = state.data.get('draft_orders', [])
    created_orders = []

    for order_idx in approved_orders:
        if order_idx < len(draft_orders):
            draft = draft_orders[order_idx]

            # Create the purchase order
            items = [{
                'product_id': item['product_id'],
                'quantity': item['quantity'],
                'unit_price': item['unit_price']
            } for item in draft['items']]

            created_order = db.create_purchase_order(
                supplier_id=draft['supplier_id'],
                items=items,
                approved_by=approved_by
            )

            created_orders.append({
                'order_id': created_order['order_id'],
                'supplier_name': draft['supplier_name'],
                'total_amount': created_order['total_amount']
            })

    state.data['created_orders'] = created_orders
    state.message = f"{len(created_orders)} bestellingen succesvol aangemaakt en goedgekeurd."
    state.step = "complete"
    state.status = "orders_placed"

    return state
