"""
New Release Detection Node
Handles detection of new vinyl releases and creates purchase order proposals
"""
from typing import Dict, Any
from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.spotify_integration import SpotifyClient


def detect_new_releases_node(state: ProcurementState) -> Dict[str, Any]:
    """
    Node for detecting new vinyl releases using the Spotify client.
    """
    print("🎵 NEW RELEASE DETECTION (Spotify)")
    db = ProcurementDatabase()
    spotify_client = SpotifyClient()
    country = getattr(state, "country", "US")
    limit = getattr(state, "limit", 5)
    new_releases_raw = spotify_client.get_new_releases(country=country, limit=limit)
    if not new_releases_raw:
        print("Geen nieuwe releases gevonden.")
        return {"new_releases": [], "next_action": "end"}
    new_releases = []
    for r in new_releases_raw:
        enriched = {**r}
        new_releases.append(enriched)
    unseen_releases = []
    for r in new_releases:
        try:
            if not db.product_exists(r['id']):
                unseen_releases.append(r)
        except AttributeError:
            unseen_releases.append(r)
    if not unseen_releases:
        print("Geen nieuwe, onbekende releases.")
        return {"new_releases": [], "next_action": "end"}
    print(f"{len(unseen_releases)} nieuwe releases gevonden.")
    return {"new_releases": unseen_releases, "next_action": "create_new_release_orders"}


def create_new_release_orders_node(state: ProcurementState) -> Dict[str, Any]:
    """
    Node for creating purchase order proposals for new releases.
    """
    print("📝 CREATE NEW RELEASE ORDERS")
    db = ProcurementDatabase()
    new_releases = getattr(state, "new_releases", [])
    proposals = []
    for release in new_releases:
        proposal = {
            "product_id": release['id'],
            "product_name": release['title'],
            "quantity": 5,
            "status": "proposed"
        }
        proposals.append(proposal)
        try:
            added_product = db.add_product({"id": release['id'], "name": release['title'], "category": "Vinyl", "supplier_id": 1, "artist": release.get('artist', 'Unknown'), "release_date": release.get('release_date')})
            db.add_inventory({"product_id": added_product['product_id'], "quantity_in_stock": 0, "reorder_level": 5})
        except AttributeError:
            pass  # Fallback: skip als methodes niet bestaan
    print(f"{len(proposals)} ordervoorstellen aangemaakt.")
    return {"purchase_order_proposals": proposals, "next_action": "human_approval"}


def check_existing_new_releases_node(state: ProcurementState) -> Dict[str, Any]:
    """
    Node for checking existing products that might be new releases needing restock.
    """
    print("📂 CHECK EXISTING NEW RELEASES")
    db = ProcurementDatabase()
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
                    'recommended_quantity': release['reorder_level'] + 5
                })
    print(f"{len(new_releases)} releases in catalog, {len(new_releases_needing_stock)} moeten bijbesteld worden.")
    result = {
        "existing_new_releases": new_releases,
        "new_releases_needing_stock": new_releases_needing_stock,
        "next_action": "create_restock_orders" if new_releases_needing_stock else "scan_for_new_releases"
    }
    return result
