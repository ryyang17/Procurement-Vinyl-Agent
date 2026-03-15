from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from langchain_google_genai import ChatGoogleGenerativeAI

db = ProcurementDatabase()
llm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0.7)

def create_purchase_order_node(state: ProcurementState) -> ProcurementState:
    """Create draft purchase orders based on supplier selections from previous node"""

    supplier_selections = state.data.get('supplier_selections', [])

    if not supplier_selections:
        state.message = "Geen leverancier selecties beschikbaar voor het maken van bestellingen."
        state.step = "complete"
        return state

    # Group by supplier
    orders_by_supplier = {}
    for selection in supplier_selections:
        supplier_id = selection['selected_supplier']['supplier_id']
        if supplier_id not in orders_by_supplier:
            orders_by_supplier[supplier_id] = {
                'supplier': selection['selected_supplier'],
                'items': [],
                'ai_recommendation': selection.get('ai_recommendation', 'Leverancier geselecteerd door AI analyse.')
            }
        orders_by_supplier[supplier_id]['items'].append({
            'product_id': selection['product_id'],
            'product_name': selection['product_name'],
            'product_code': selection['product_code'],
            'quantity': selection['reorder_qty'],
            'unit_price': selection['selected_supplier']['price_per_unit']
        })

    # Create draft purchase orders
    draft_orders = []
    for supplier_id, order_data in orders_by_supplier.items():
        total = sum(item['quantity'] * item['unit_price'] for item in order_data['items'])

        draft_orders.append({
            'supplier_id': supplier_id,
            'supplier_name': order_data['supplier']['supplier_name'],
            'items': order_data['items'],
            'total_amount': total,
            'ai_recommendation': order_data['ai_recommendation'],
            'lead_time_days': order_data['supplier']['lead_time_days'],
            'quality_rating': order_data['supplier']['quality_rating']
        })

    state.data['draft_orders'] = draft_orders
    state.message = f"{len(draft_orders)} conceptbestellingen aangemaakt, wachten op goedkeuring."
    state.step = "human_approval"
    state.status = "awaiting_approval"

    return state
