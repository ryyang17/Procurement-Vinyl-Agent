from typing import Dict, Any
from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.spotify_integration import SpotifyClient


def detect_new_releases_node(state: ProcurementState) -> ProcurementState:
    """
    Node for detecting new vinyl releases using the Spotify client.
    """
    print("🎵 NEW RELEASE DETECTION (Spotify)")
    db = ProcurementDatabase()
    spotify_client = SpotifyClient()

    new_releases_raw = spotify_client.get_new_releases(country=state.country, limit=state.limit)
    if not new_releases_raw:
        print("Geen nieuwe releases gevonden.")
        state.new_releases = []
        state.next_action = "end"
        state.message = "Geen nieuwe releases gevonden via Spotify API."
        state.status = "ok"
        state.step = "complete"
        return state

    new_releases = []
    seen_release_ids = set()

    for r in new_releases_raw:
        release_id = r.get('id')
        if release_id in seen_release_ids:
            continue
        seen_release_ids.add(release_id)

        enriched = {**r}
        enriched['source_type'] = 'new_release_spotify'
        enriched['category'] = r.get('category') or r.get('genre') or 'New Release'
        new_releases.append(enriched)

    # Filter out existing products
    unseen_releases = []
    for r in new_releases:
        try:
            if not db.product_exists(r['id']):
                unseen_releases.append(r)
        except AttributeError:
            unseen_releases.append(r)

    if not unseen_releases:
        print("Geen nieuwe, onbekende releases.")
        state.new_releases = []
        state.message = "Alle releases zijn al bekend in de database."
        state.status = "ok"
        state.step = "complete"
        return state

    print(f"{len(unseen_releases)} nieuwe releases gevonden.")
    state.new_releases = unseen_releases
    state.next_action = "create_new_release_orders"
    state.message = f"{len(unseen_releases)} nieuwe releases voor evaluatie gevonden."
    state.status = "new_releases_detected"
    state.step = "create_new_release_orders"

    return state


def create_new_release_orders_node(state: ProcurementState) -> ProcurementState:
    """
    Node for creating purchase order proposals for new releases.
    """
    print("📝 CREATE NEW RELEASE ORDERS")
    db = ProcurementDatabase()

    if not state.new_releases:
        state.data["purchase_order_proposals"] = []
        state.data["draft_orders"] = []
        state.message = "Geen nieuwe releases om bestelvoorstellen voor te maken."
        state.step = "complete"
        state.status = "ok"
        return state

    proposals = []
    draft_orders = []

    for release in state.new_releases:
        title = release.get("title", "Unknown Release")
        spotify_id = release.get("id")
        artist = release.get("artist", "Unknown")
        category = release.get("category") or release.get("genre") or "New Release"
        source_type = release.get("source_type", "new_release_spotify")

        # Re-use bestaand product als het al in catalogus staat, anders toevoegen.
        products = db.get_products()
        existing_product = next(
            (p for p in products if p.get("id") == spotify_id or p.get("product_id") == spotify_id),
            None,
        )

        if existing_product:
            product_id = existing_product.get("product_id")
        else:
            added_product = db.add_product(
                {
                    "id": spotify_id,
                    "name": title,
                    "category": category,
                    "supplier_id": 1,
                    "artist": artist,
                    "release_date": release.get("release_date"),
                }
            )
            product_id = added_product["product_id"]
            db.add_inventory({"product_id": product_id, "quantity_in_stock": 0, "reorder_level": 5})

        supplier_options = db.get_suppliers_for_product(product_id)
        if supplier_options:
            selected_supplier = min(supplier_options, key=lambda s: s.get("price_per_unit", 0))
            unit_price = selected_supplier.get("price_per_unit", 0)
            supplier_id = selected_supplier.get("supplier_id", 1)
            supplier_name = selected_supplier.get("supplier_name", "Unknown")
            lead_time_days = selected_supplier.get("lead_time_days")
            quality_rating = selected_supplier.get("quality_rating")
        else:
            unit_price = 0
            supplier_id = 1
            supplier_name = "Unknown"
            lead_time_days = None
            quality_rating = None

        quantity = 5
        proposals.append(
            {
                "product_id": product_id,
                "product_name": title,
                "artist": artist,
                "category": category,
                "source_type": source_type,
                "quantity": quantity,
                "status": "proposed",
            }
        )

        # Use the new helper method to ensure proper path tracking
        new_release_order = {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "items": [
                {
                    "product_id": product_id,
                    "product_name": title,
                    "category": category,
                    "source_type": source_type,
                    "quantity": quantity,
                    "unit_price": unit_price,
                }
            ],
            "total_amount": quantity * unit_price,
            "source_type": source_type,
            "ai_recommendation": (
                f"Nieuwe release van {artist} ({category}); aanbevolen startvoorraad {quantity} stuks."
            ),
            "lead_time_days": lead_time_days,
            "quality_rating": quality_rating,
        }

        state.add_new_release_order(new_release_order)

    state.data["purchase_order_proposals"] = proposals
    state.purchase_order_proposals = proposals  # Also populate root level
    state.message = f"{len(draft_orders)} conceptbestellingen voor nieuwe releases aangemaakt, wachten op goedkeuring."
    state.step = "human_approval"
    state.status = "awaiting_approval"
    state.awaiting_human_approval = True

    return state


def check_existing_new_releases_node(state: ProcurementState) -> ProcurementState:
    """
    Node for checking existing products that might be new releases needing restock.
    """
    print("📂 CHECK EXISTING NEW RELEASES")
    db = ProcurementDatabase()

    # Clear new release path data to prevent mixing with supplier path
    state.clear_path_data("new_releases")

    try:
        new_releases = db.detect_new_releases()
    except AttributeError:
        new_releases = []

    try:
        low_stock_products = db.get_low_stock_products()
    except AttributeError:
        low_stock_products = []

    new_releases_needing_stock = []

    for release in new_releases:
        if release.get('needs_reorder', False):
            try:
                supplier_options = db.get_suppliers_for_product(release['product_id'])
            except AttributeError:
                supplier_options = []

            if supplier_options:
                best_supplier = min(supplier_options, key=lambda s: s['price_per_unit'])
                new_releases_needing_stock.append({
                    'release': release,
                    'supplier': best_supplier,
                    'recommended_quantity': release['reorder_level'] + 5,
                    'source_type': 'existing_inventory_new_release',
                    'category': release.get('category', 'Unknown'),
                })

    print(f"{len(new_releases)} releases in catalog, {len(new_releases_needing_stock)} moeten bijbesteld worden.")

    # Update state with findings
    state.existing_new_releases = new_releases
    state.new_releases_needing_stock = new_releases_needing_stock

    if new_releases_needing_stock:
        state.next_action = "create_restock_orders"
        state.message = f"{len(new_releases_needing_stock)} bestaande releases hebben voorraad nodig."
        state.status = "existing_releases_need_stock"
        state.step = "detect_new_releases"
    else:
        state.next_action = "detect_new_releases"
        state.message = f"Bestaande {len(new_releases)} releases hebben genoeg voorraad. Zoeken naar nieuwe releases..."
        state.status = "checking_spotify"
        state.step = "detect_new_releases"

    return state
