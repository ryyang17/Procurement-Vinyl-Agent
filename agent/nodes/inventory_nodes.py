import json
import os
from agent.models import ProcurementState, ReorderProposal

def load_json(filename):
    db_path = os.path.join(os.path.dirname(__file__), '../../db', filename)
    with open(db_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def daily_inventory_check_node(state: ProcurementState) -> ProcurementState:

    inventory = load_json('inventory.json')
    products = load_json('product.json')
    product_map = {p['product_id']: p for p in products}
    proposals = []
    for item in inventory:
        qty = item['quantity_in_stock']
        min_qty = item['reorder_level']
        if qty <= min_qty:
            prod = product_map.get(item['product_id'])
            reorder_qty = max(1, min_qty * 2 - qty)  # bestel genoeg om voorraad te verdubbelen boven het minimum
            proposals.append(ReorderProposal(
                product_code=prod['sku'],
                product_name=prod['name'],
                current_qty=qty,
                reorder_qty=reorder_qty,
                min_threshold=min_qty
            ))
    if proposals:
        msg = f"Voorstel: bestel bij voor {len(proposals)} producten met lage voorraad."
        state.data['reorder_proposals'] = [p.dict() for p in proposals]
        state.message = msg
        state.status = 'proposed'
    else:
        state.message = "Alle voorraden zijn boven het minimum. Geen actie nodig."
        state.status = 'ok'
    return state
