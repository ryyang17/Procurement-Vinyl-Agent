from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.utils.memory import log_decision, update_supplier_performance_on_rejection, get_all_decisions
from datetime import datetime, timezone

db = ProcurementDatabase()

def human_approval_node(state: ProcurementState) -> ProcurementState:
    print("✅ DEBUG: human_approval_node - Auto-approving alle orders!")

    draft_orders = state.data.get('draft_orders', [])

    if not draft_orders:
        print("   -> Geen bestellingen om goed te keuren")
        state.message = "Geen bestellingen om goed te keuren."
        state.step = "complete"
        state.status = "ok"
        return state

    # AUTO-APPROVE all orders (no more waiting!)
    print(f"   -> Auto-approving {len(draft_orders)} bestellingen")
    state.approval_order_indices = list(range(len(draft_orders)))
    state.rejection_reasons_by_index = {}
    state.awaiting_human_approval = False
    state.message = f"✅ AUTO-APPROVED: Alle {len(draft_orders)} bestellingen automatisch goedgekeurd!"
    state.step = "processing_approval"
    state.status = "approved"
    
    return state

    # Reset approval fields for next interaction
    state.approval_order_indices = []
    state.rejection_reasons_by_index = {}

    return state

def _process_approval_logic(state: ProcurementState, approved_orders: list, approved_by: str, rejection_reasons: dict, approval_decision: str = 'approved') -> ProcurementState:
    approved_orders = [int(idx) for idx in approved_orders]
    normalized_rejection_reasons = {}
    for order_idx, reason in rejection_reasons.items():
        try:
            normalized_rejection_reasons[int(order_idx)] = reason
        except (TypeError, ValueError):
            continue

    if not approved_orders and not rejection_reasons:
        state.message = "Geen bestellingen goedgekeurd."
        state.step = "complete"
        state.status = "cancelled"
        state.data['decision_history'] = get_all_decisions(limit=10)
        state.data['order_history'] = db.get_order_history(limit=20)
        return state

    draft_orders = state.data.get('draft_orders', [])
    created_orders = []

    # Log in memory
    if normalized_rejection_reasons:
        for order_idx, reason in normalized_rejection_reasons.items():
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

            log_decision(
                decision_type='supplier_approved',
                supplier_id=draft.get('supplier_id'),
                supplier_name=draft.get('supplier_name'),
                po_id=created_order.get('purchase_order_id', created_order.get('order_id')),
                context={'items_count': len(items)},
                actor=approved_by
            )

            created_orders.append({
                'order_id': created_order.get('purchase_order_id', created_order.get('order_id')),
                'supplier_name': draft['supplier_name'],
                'total_amount': created_order['total_amount']
            })

    state.data['created_orders'] = created_orders
    state.data['decision_history'] = get_all_decisions(limit=10)
    state.data['order_history'] = db.get_order_history(limit=20)
    state.message = f"{len(created_orders)} bestellingen succesvol aangemaakt en goedgekeurd."
    state.step = "complete"
    state.status = "orders_placed"
    state.approval_decision = approval_decision
    state.approved_by = approved_by

    return state

def process_approval_node_workflow(state: ProcurementState) -> ProcurementState:

    # Use approval_order_indices and rejection_reasons_by_index from frontend
    approved_orders = getattr(state, 'approval_order_indices', [])
    rejection_reasons = getattr(state, 'rejection_reasons_by_index', {})
    if not approved_orders:
        approved_orders = getattr(state, 'approved_orders', [])
    if not rejection_reasons:
        rejection_reasons = getattr(state, 'rejection_reasons', {})
    approved_by = getattr(state, 'approved_by', 'manager')

    # Reset flags zodat node niet oneindige loop maakt
    state.awaiting_human_approval = False
    state.approval_order_indices = []
    state.rejection_reasons_by_index = {}

    return _process_approval_logic(state, approved_orders, approved_by, rejection_reasons, approval_decision='processed')


def process_approval_node(state: ProcurementState, approved_orders: list, approved_by: str = "manager", rejection_reasons: dict = None) -> ProcurementState:

    if rejection_reasons is None:
        rejection_reasons = {}
    return _process_approval_logic(state, approved_orders, approved_by, rejection_reasons, approval_decision='approved')
