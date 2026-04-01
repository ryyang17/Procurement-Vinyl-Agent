from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from datetime import datetime, timedelta

db = ProcurementDatabase()


NEW_RELEASE_WINDOW_DAYS = 5


def _parse_iso_datetime(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(str(raw_value).replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _is_recent_release(selection: dict) -> bool:
    cutoff = datetime.now() - timedelta(days=NEW_RELEASE_WINDOW_DAYS)
    release_dt = _parse_iso_datetime(selection.get('release_date'))
    created_dt = _parse_iso_datetime(selection.get('created_at'))
    if release_dt and release_dt >= cutoff:
        return True
    if created_dt and created_dt >= cutoff:
        return True
    return False


def _selection_order_type(selection: dict) -> str:
    source = str(selection.get('source_type', '')).lower()
    order_path = str(selection.get('order_path', '')).lower()
    if 'new_release' in source or 'new_release' in order_path:
        return 'new_releases'
    if _is_recent_release(selection):
        return 'new_releases'
    return 'suppliers'

def create_purchase_order_node(state: ProcurementState) -> ProcurementState:
    """Create draft purchase orders based on supplier selections from previous node"""
    supplier_selections = state.data.get('supplier_selections', [])
    existing_draft_orders = list(state.data.get('draft_orders', []))

    if not supplier_selections:
        if existing_draft_orders:
            state.message = (
                f"{len(existing_draft_orders)} conceptbestelling(en) klaar "
                "(new releases). Wachten op goedkeuring."
            )
            state.step = "human_approval"
            state.status = "awaiting_approval"
            state.awaiting_human_approval = True
        else:
            state.message = "Geen leverancier selecties beschikbaar voor het maken van bestellingen."
            state.step = "complete"
            state.status = "ok"
        return state

    # Clean supplier path to prevent cross-contamination
    state.clear_path_data("suppliers")

    # Group by supplier + order type so new-release and reorder orders stay separated.
    orders_by_supplier = {}
    for selection in supplier_selections:
        supplier_id = selection['selected_supplier']['supplier_id']
        order_type = _selection_order_type(selection)
        grouping_key = (supplier_id, order_type)
        if grouping_key not in orders_by_supplier:
            orders_by_supplier[grouping_key] = {
                'supplier': selection['selected_supplier'],
                'items': [],
                'ai_recommendation': selection.get('ai_recommendation', 'Leverancier geselecteerd door AI analyse.'),
                'order_type': order_type,
            }
        orders_by_supplier[grouping_key]['items'].append({
            'product_id': selection['product_id'],
            'product_name': selection['product_name'],
            'product_code': selection['product_code'],
            'category': selection.get('category', 'Unknown'),
            'source_type': 'new_releases' if order_type == 'new_releases' else 'inventory_low_stock',
            'order_path': 'new_releases' if order_type == 'new_releases' else 'suppliers',
            'release_date': selection.get('release_date'),
            'created_at': selection.get('created_at'),
            'market_popularity_score': selection.get('market_popularity_score'),
            'quantity': selection['reorder_qty'],
            'unit_price': selection['selected_supplier']['price_per_unit']
        })

    # Create draft purchase orders using path-specific method
    for (supplier_id, _order_type), order_data in orders_by_supplier.items():
        total = sum(item['quantity'] * item['unit_price'] for item in order_data['items'])
        order_type = order_data.get('order_type', 'suppliers')
        popularity_values = [
            float(item.get('market_popularity_score'))
            for item in order_data['items']
            if isinstance(item.get('market_popularity_score'), (int, float))
        ]
        max_popularity = max(popularity_values) if popularity_values else None

        supplier_order = {
            'supplier_id': supplier_id,
            'supplier_name': order_data['supplier']['supplier_name'],
            'source_type': 'new_releases' if order_type == 'new_releases' else 'inventory_low_stock',
            'order_path': 'new_releases' if order_type == 'new_releases' else 'suppliers',
            'items': order_data['items'],
            'total_amount': total,
            'ai_recommendation': order_data['ai_recommendation'],
            'lead_time_days': order_data['supplier']['lead_time_days'],
            'quality_rating': order_data['supplier']['quality_rating'],
            'market_popularity_score': max_popularity,
        }

        # Use path-specific methods to keep source labels correct in memory and frontend.
        if order_type == 'new_releases':
            state.add_new_release_order(supplier_order)
        else:
            state.add_supplier_order(supplier_order)

    # Update state
    supplier_orders = state.get_supplier_orders()
    total_draft_orders = len(state.data.get('draft_orders', []))
    new_release_orders = len(state.get_new_release_orders())
    state.message = (
        f"{len(supplier_orders)} reorder conceptbestellingen en "
        f"{new_release_orders} new-release conceptbestellingen klaar "
        f"(totaal {total_draft_orders}). Wachten op goedkeuring."
    )
    state.step = "human_approval"
    state.status = "awaiting_approval"
    state.awaiting_human_approval = True

    return state
