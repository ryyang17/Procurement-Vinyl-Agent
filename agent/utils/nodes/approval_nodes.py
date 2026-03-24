from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.utils.memory import log_decision, update_supplier_performance_on_rejection
from datetime import datetime, timezone
from langgraph.types import interrupt

db = ProcurementDatabase()

def human_approval_node(state: ProcurementState) -> ProcurementState:

    draft_orders = state.data.get('draft_orders', [])
    approval_order_indices = getattr(state, 'approval_order_indices', [])
    rejection_reasons_by_index = getattr(state, 'rejection_reasons_by_index', {})

    if not draft_orders:
        state.message = "Geen bestellingen om goed te keuren."
        state.step = "complete"
        state.status = "ok"
        return state

    # Als user al gereageerd heeft op approvals (via frontend) → skip dit node
    # het wordt verwerkt in route_after_approval
    if approval_order_indices or rejection_reasons_by_index:
        state.message = f"Goedkeuringen ontvangen: {len(approval_order_indices)} goedgekeurd"
        state.step = "processing_approval"
        return state

    # Pause execution and wait for an explicit resume command from the frontend.
    state.awaiting_human_approval = True
    state.message = f"{len(draft_orders)} bestellingen wachten op goedkeuring."

    state.step = "awaiting_human_input"
    state.status = "awaiting_approval"
    state.approval_requested_at = datetime.now(timezone.utc).isoformat()

    # Reset approval fields for next interaction
    state.approval_order_indices = []
    state.rejection_reasons_by_index = {}

    decision = interrupt({
        'kind': 'approval_decision',
        'thread_id': getattr(state, 'thread_id', None),
        'draft_orders_count': len(draft_orders),
        'message': state.message,
    })

    if isinstance(decision, dict):
        approved_indices = decision.get('approval_order_indices') or decision.get('approved_indices') or []
        rejection_reasons = decision.get('rejection_reasons_by_index') or {}
        approved_by = decision.get('approved_by') or 'manager'
        approval_decision = decision.get('approval_decision') or decision.get('decision')
    else:
        approved_indices = []
        rejection_reasons = {}
        approved_by = 'manager'
        approval_decision = 'rejected'

    if not isinstance(approved_indices, list):
        approved_indices = []
    if not isinstance(rejection_reasons, dict):
        rejection_reasons = {}

    state.awaiting_human_approval = False
    state.approval_order_indices = [int(idx) for idx in approved_indices if isinstance(idx, int) or (isinstance(idx, str) and idx.isdigit())]
    state.rejection_reasons_by_index = {
        int(idx): str(reason)
        for idx, reason in rejection_reasons.items()
        if (isinstance(idx, int) or (isinstance(idx, str) and idx.isdigit()))
    }
    state.approved_by = str(approved_by)
    if approval_decision is not None:
        state.approval_decision = str(approval_decision)
    state.step = 'processing_approval'
    state.status = 'in_progress'

    return state

def _process_approval_logic(state: ProcurementState, approved_orders: list, approved_by: str, rejection_reasons: dict, approval_decision: str = 'approved') -> ProcurementState:
    if not approved_orders and not rejection_reasons:
        state.message = "Geen bestellingen goedgekeurd."
        state.step = "complete"
        state.status = "cancelled"
        return state

    draft_orders = state.data.get('draft_orders', [])
    created_orders = []

    # Log in memory
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
