from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.utils.memory import log_decision, update_supplier_performance_on_rejection
from datetime import datetime, timezone

db = ProcurementDatabase()

def human_approval_node(state: ProcurementState) -> ProcurementState:
    """
    R6: Human must approve each order
    R7: Show supplier, quantity, total price
    R8: Order only placed after approval

    This node pauses the workflow and waits for human approval
    """
    draft_orders = state.data.get('draft_orders', [])

    if not draft_orders:
        state.message = "Geen bestellingen om goed te keuren."
        state.step = "complete"
        state.status = "ok"
        return state

    # Set the step to indicate we're awaiting approval
    # The workflow will pause here and return control to the user
    state.message = f"{len(draft_orders)} bestellingen wachten op goedkeuring."
    state.step = "awaiting_human_input"
    state.status = "awaiting_approval"
    state.approval_requested_at = datetime.now(timezone.utc).isoformat()

    return state

def process_approval_node_workflow(state: ProcurementState) -> ProcurementState:
    """
    Workflow version of process_approval that reads approval data from state
    This is called by the workflow graph after human approval decision is made
    """
    # Read approval data from state
    approved_orders = getattr(state, 'approved_orders', [])
    approved_by = getattr(state, 'approved_by', 'manager')
    rejection_reasons = getattr(state, 'rejection_reasons', {})

    if not approved_orders and not rejection_reasons:
        state.message = "Geen bestellingen goedgekeurd."
        state.step = "complete"
        state.status = "cancelled"
        return state

    draft_orders = state.data.get('draft_orders', [])
    created_orders = []

    # Log rejections in memory and update supplier performance
    if rejection_reasons:
        for order_idx, reason in rejection_reasons.items():
            if order_idx < len(draft_orders):
                draft = draft_orders[order_idx]
                supplier_id = draft.get('supplier_id')
                supplier_name = draft.get('supplier_name')

                # Log the rejection decision
                log_decision(
                    decision_type='supplier_rejected',
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    reason=reason,
                    context={'draft_order_idx': order_idx},
                    actor=approved_by
                )

                # Update supplier performance based on rejection reason
                update_supplier_performance_on_rejection(
                    supplier_id=supplier_id,
                    rejection_reason=reason
                )

    # Log approvals and create orders
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

            # Log approval in memory - use correct order_id field
            log_decision(
                decision_type='supplier_approved',
                supplier_id=draft.get('supplier_id'),
                supplier_name=draft.get('supplier_name'),
                po_id=created_order['purchase_order_id'],  # Use purchase_order_id instead of order_id
                context={'items_count': len(items)},
                actor=approved_by
            )

            created_orders.append({
                'order_id': created_order['purchase_order_id'],
                'supplier_name': draft['supplier_name'],
                'total_amount': created_order['total_amount']
            })

    state.data['created_orders'] = created_orders
    state.message = f"{len(created_orders)} bestellingen succesvol aangemaakt en goedgekeurd."
    state.step = "complete"
    state.status = "orders_placed"
    state.approval_decision = 'processed'  # Mark as processed

    return state

def process_approval_node(state: ProcurementState, approved_orders: list, approved_by: str = "manager", rejection_reasons: dict = None) -> ProcurementState:
    """
    Main.py version - Process the human approval decisions and create actual purchase orders

    Args:
        state: Current procurement state
        approved_orders: List of indices that were approved
        approved_by: Name of the approver
        rejection_reasons: Dict mapping rejected order indices to rejection reasons
    """
    if not approved_orders and not rejection_reasons:
        state.message = "Geen bestellingen goedgekeurd."
        state.step = "complete"
        state.status = "cancelled"
        return state

    draft_orders = state.data.get('draft_orders', [])
    created_orders = []

    # Log rejections in memory and update supplier performance
    if rejection_reasons:
        for order_idx, reason in rejection_reasons.items():
            if order_idx < len(draft_orders):
                draft = draft_orders[order_idx]
                supplier_id = draft.get('supplier_id')
                supplier_name = draft.get('supplier_name')

                # Log the rejection decision
                log_decision(
                    decision_type='supplier_rejected',
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    reason=reason,
                    context={'draft_order_idx': order_idx},
                    actor=approved_by
                )

                # Update supplier performance based on rejection reason
                update_supplier_performance_on_rejection(
                    supplier_id=supplier_id,
                    rejection_reason=reason
                )

    # Log approvals and create orders
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

            # Log approval in memory
            log_decision(
                decision_type='supplier_approved',
                supplier_id=draft.get('supplier_id'),
                supplier_name=draft.get('supplier_name'),
                po_id=created_order['order_id'],
                context={'items_count': len(items)},
                actor=approved_by
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
    state.approval_decision = 'approved'
    state.approved_by = approved_by

    return state


