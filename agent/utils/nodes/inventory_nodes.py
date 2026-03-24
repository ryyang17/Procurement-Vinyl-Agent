from agent.utils.state import ProcurementState, ReorderProposal
from agent.procurement_data import ProcurementDatabase


MAX_REORDER_PROPOSALS = 15


def _normalize_path_choice(path_choice: str | None) -> str | None:
    if path_choice is None:
        return None

    aliases = {
        "path_1_suppliers": "path_1_suppliers",
        "find_suppliers": "path_1_suppliers",
        "suppliers": "path_1_suppliers",
        "path_2_new_releases": "path_2_new_releases",
        "check_existing_new_releases": "path_2_new_releases",
        "new_releases": "path_2_new_releases",
    }
    return aliases.get(str(path_choice).strip(), None)

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

    # Preserve a UI-selected path choice when a run is resumed from the frontend.
    # If no valid choice is present, reset the path fields for a clean selection step.
    selected_path = _normalize_path_choice(getattr(state, "path_choice", None))
    if selected_path is not None:
        state.path_choice = selected_path
        state.awaiting_path_selection = False
    else:
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
        dynamic_levels = state.data.get('dynamic_reorder_levels', {})
        min_qty = dynamic_levels.get(str(item.get('product_id')), item.get('reorder_level', 0))
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
                    'reorder_basis': 'sales_velocity' if str(product_id) in dynamic_levels else 'static_threshold',
                })
                seen_product_ids.add(product_id)

    # Keep only the most urgent low-stock proposals when many products are below threshold.
    if len(proposals) > MAX_REORDER_PROPOSALS:
        ranked_pairs = sorted(
            zip(proposals, proposal_dicts),
            key=lambda pair: pair[0].reorder_qty,
            reverse=True,
        )
        ranked_pairs = ranked_pairs[:MAX_REORDER_PROPOSALS]
        proposals = [pair[0] for pair in ranked_pairs]
        proposal_dicts = [pair[1] for pair in ranked_pairs]

    # Update state with findings
    if proposals:
        state.data['reorder_proposals'] = proposal_dicts

        # Update UI helper fields for display
        state.inventory_alerts = [
            f"{p.product_name} [{proposal_dicts[i].get('category', 'Unknown')}] - {p.current_qty} op voorraad (min {p.min_threshold}), voorstel {p.reorder_qty} (Inventory)"
            for i, p in enumerate(proposals)
        ]

        state.message = f"Voorstel: bestel bij voor {len(proposals)} producten met lage voorraad (max {MAX_REORDER_PROPOSALS})."
        state.status = 'proposed'
    else:
        state.data['reorder_proposals'] = []
        state.inventory_alerts = []
        state.message = "Alle voorraden zijn boven het minimum. Geen actie nodig."
        state.status = 'ok'

    return state
