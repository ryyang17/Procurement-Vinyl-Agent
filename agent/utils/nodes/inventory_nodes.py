import json
import os
from agent.utils.state import ProcurementState, ReorderProposal
from agent.procurement_data import ProcurementDatabase

def daily_inventory_check_node(state: ProcurementState) -> ProcurementState:
    """
    Check inventory levels and identify products that need reordering.
    Always reads fresh data from disk to ensure latest state after deliveries.
    """
    # Use ProcurementDatabase to get the freshest data
    db = ProcurementDatabase()

    try:
        inventory = db.get_inventory()
        products = db.get_products()
    except Exception as e:
        state.errors.append(f"Failed to load inventory data: {str(e)}")
        state.message = "Fout bij laden van voorraadinformatie."
        state.status = "error"
        return state

    product_map = {p['product_id']: p for p in products}
    proposals = []

    for item in inventory:
        # Use quantity_in_stock as the current quantity
        qty = item.get('quantity_in_stock', 0)
        min_qty = item.get('reorder_level', 0)
        product_id = item.get('product_id')

        # Check if quantity is at or below reorder level
        if qty <= min_qty:
            prod = product_map.get(product_id)
            if prod:
                # Calculate reorder quantity to bring stock above minimum
                reorder_qty = max(1, min_qty * 2 - qty)

                proposals.append(ReorderProposal(
                    product_code=prod.get('sku', 'N/A'),
                    product_name=prod.get('name', 'Unknown'),
                    current_qty=qty,
                    reorder_qty=reorder_qty,
                    min_threshold=min_qty
                ))

    # Update state with findings
    if proposals:
        msg = f"Voorstel: bestel bij voor {len(proposals)} producten met lage voorraad."
        state.data['reorder_proposals'] = [p.dict() for p in proposals]
        state.message = msg
        state.status = 'proposed'
    else:
        state.message = "Alle voorraden zijn boven het minimum. Geen actie nodig."
        state.status = 'ok'

    return state
