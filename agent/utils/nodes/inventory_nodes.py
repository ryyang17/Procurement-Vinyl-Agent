from agent.utils.state import ProcurementState, ReorderProposal
from agent.procurement_data import ProcurementDatabase

def daily_inventory_check_node(state: ProcurementState) -> ProcurementState:

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
    proposal_dicts = []
    seen_product_ids = set()

    # Start every inventory cycle with clean path selection to avoid stale checkpoint routing.
    state.path_choice = None
    state.awaiting_path_selection = False

    # Clear ALL path-specific artifacts so UI doesn't mix supplier and new-release flows.
    state.clear_path_data("suppliers")
    state.clear_path_data("new_releases")

    # Also reset workflow-specific state
    if 'supplier_selections' not in state.data:
        state.data['supplier_selections'] = []
    if 'purchase_order_proposals' not in state.data:
        state.data['purchase_order_proposals'] = []
    if 'created_orders' not in state.data:
        state.data['created_orders'] = []

    for item in inventory:
        # Use quantity_in_stock as the current quantity
        qty = item.get('quantity_in_stock', 0)
        min_qty = item.get('reorder_level', 0)
        product_id = item.get('product_id')

        if product_id in seen_product_ids:
            continue

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
                proposal_dicts.append({
                    **proposals[-1].model_dump(),
                    'product_id': product_id,
                    'category': prod.get('category', 'Unknown'),
                    'source_type': 'inventory_low_stock',
                })
                seen_product_ids.add(product_id)

    # Update state with findings
    if proposals:
        state.data['reorder_proposals'] = proposal_dicts

        # Update UI helper fields for display
        state.inventory_alerts = [
            f"{p.product_name} [{proposal_dicts[i].get('category', 'Unknown')}] - {p.current_qty} op voorraad (min {p.min_threshold}), voorstel {p.reorder_qty} (Inventory)"
            for i, p in enumerate(proposals)
        ]

        state.message = f"Voorstel: bestel bij voor {len(proposals)} producten met lage voorraad."
        state.status = 'proposed'
    else:
        state.data['reorder_proposals'] = []
        state.inventory_alerts = []
        state.message = "Alle voorraden zijn boven het minimum. Geen actie nodig."
        state.status = 'ok'

    return state
