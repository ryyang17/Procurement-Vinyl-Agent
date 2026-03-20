from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
import os

db = ProcurementDatabase()

def create_purchase_order_node(state: ProcurementState) -> ProcurementState:
    """Create draft purchase orders based on supplier selections from previous node"""
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-pro-preview",
        temperature=0.7,
        api_key=os.getenv("GOOGLE_API_KEY")
    )

    supplier_selections = state.data.get('supplier_selections', [])

    if not supplier_selections:
        state.message = "Geen leverancier selecties beschikbaar voor het maken van bestellingen."
        state.step = "complete"
        state.status = "ok"
        return state

    # Clean supplier path to prevent cross-contamination
    state.clear_path_data("suppliers")

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
            'category': selection.get('category', 'Unknown'),
            'source_type': selection.get('source_type', 'inventory_low_stock'),
            'quantity': selection['reorder_qty'],
            'unit_price': selection['selected_supplier']['price_per_unit']
        })

    # Create draft purchase orders using path-specific method
    for supplier_id, order_data in orders_by_supplier.items():
        total = sum(item['quantity'] * item['unit_price'] for item in order_data['items'])

        supplier_order = {
            'supplier_id': supplier_id,
            'supplier_name': order_data['supplier']['supplier_name'],
            'source_type': 'inventory_low_stock',
            'items': order_data['items'],
            'total_amount': total,
            'ai_recommendation': order_data['ai_recommendation'],
            'lead_time_days': order_data['supplier']['lead_time_days'],
            'quality_rating': order_data['supplier']['quality_rating']
        }

        # Use the path-specific helper method
        state.add_supplier_order(supplier_order)

    # Update state
    supplier_orders = state.get_supplier_orders()
    state.message = f"{len(supplier_orders)} conceptbestellingen voor leveranciers aangemaakt, wachten op goedkeuring."
    state.step = "human_approval"
    state.status = "awaiting_approval"
    state.awaiting_human_approval = True

    return state
