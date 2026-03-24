from typing import Dict, Any
from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.spotify_integration import SpotifyClient


TOTAL_PROPOSAL_CAP = 15
RESERVED_NEW_RELEASE_SLOTS = 5
MAX_REORDER_PROPOSALS = TOTAL_PROPOSAL_CAP


def _state_get(state: ProcurementState, key: str, default):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _remaining_global_slots(state: ProcurementState) -> int:
    data = _state_get(state, "data", {}) or {}
    low_stock_reorders = data.get("reorder_proposals", [])
    used_slots = len(low_stock_reorders)
    return max(0, TOTAL_PROPOSAL_CAP - used_slots)


def market_popularity_node(state: ProcurementState) -> Dict[str, Any]:
    """
    Node for market popularity analysis using Spotify.
    Runs before the new-release check to enrich procurement decisions.
    """
    print("📈 MARKET POPULARITY ANALYSIS (Spotify)")
    db = ProcurementDatabase()
    spotify_client = SpotifyClient()

    remaining_slots = _remaining_global_slots(state)
    if remaining_slots == 0:
        print("Globale limiet bereikt via lage-voorraad voorstellen; market popularity wordt overgeslagen.")
        return {
            "market_popular_albums": [],
            "uncatalogued_popular_albums": [],
            "market_popularity_alerts": [],
        }

    country = getattr(state, "country", "US")
    market_limit = min(remaining_slots, max(8, int(getattr(state, "limit", 5)) * 2))
    market_popular_albums = spotify_client.get_market_popular_albums(country=country, limit=market_limit)

    if not market_popular_albums:
        print("Geen populaire albums gevonden voor deze markt.")
        return {
            "market_popular_albums": [],
            "uncatalogued_popular_albums": [],
            "market_popularity_alerts": [],
        }

    uncatalogued_popular_albums = []
    for album in market_popular_albums:
        try:
            if not db.product_exists(album["id"]):
                uncatalogued_popular_albums.append(album)
        except AttributeError:
            uncatalogued_popular_albums.append(album)

    market_popularity_alerts = [
        f"Markttrend: {a.get('title', 'Unknown')}"
        for a in market_popular_albums[:3]
    ]

    print(
        f"{len(market_popular_albums)} marktpopulaire albums geanalyseerd, "
        f"{len(uncatalogued_popular_albums)} nog niet in catalogus."
    )
    return {
        "market_popular_albums": market_popular_albums,
        "uncatalogued_popular_albums": uncatalogued_popular_albums,
        "market_popularity_alerts": market_popularity_alerts,
    }


def detect_new_releases_node(state: ProcurementState) -> Dict[str, Any]:
    """
    Node for detecting new vinyl releases using the Spotify client.
    """
    print("🎵 NEW RELEASE DETECTION (Spotify)")
    db = ProcurementDatabase()
    spotify_client = SpotifyClient()
    remaining_slots = _remaining_global_slots(state)
    if remaining_slots == 0:
        print("Globale limiet bereikt via lage-voorraad voorstellen; geen nieuwe releases toevoegen.")
        return {"new_releases": [], "next_action": "find_suppliers"}

    country = getattr(state, "country", "US")
    limit = min(remaining_slots, getattr(state, "limit", 5))
    new_releases_raw = spotify_client.get_new_releases(country=country, limit=limit)
    uncatalogued_popular_albums = getattr(state, "uncatalogued_popular_albums", [])

    if not new_releases_raw:
        # Keep market-trending albums as candidates even if Spotify new-release fetch is empty.
        new_releases_raw = []

    new_releases = []
    for r in new_releases_raw:
        enriched = {**r}
        new_releases.append(enriched)

    # Merge uncatalogued market-popular albums as additional candidates.
    by_id = {r.get("id"): r for r in new_releases if r.get("id")}
    for album in uncatalogued_popular_albums:
        album_id = album.get("id")
        if not album_id:
            continue

        if album_id in by_id:
            by_id[album_id]["market_popularity_score"] = album.get("market_popularity_score")
            by_id[album_id]["market_popularity_source"] = "spotify_market_popularity"
        else:
            by_id[album_id] = {
                "id": album_id,
                "title": album.get("title"),
                "artist": album.get("artist"),
                "genre": album.get("genre", "Unknown"),
                "category": album.get("genre", "New Release") or "New Release",
                "release_date": album.get("release_date"),
                "total_tracks": album.get("total_tracks"),
                "external_url": album.get("external_url"),
                "artist_popularity": album.get("artist_popularity"),
                "market_popularity_score": album.get("market_popularity_score"),
                "market_popularity_source": "spotify_market_popularity",
            }

    new_releases = list(by_id.values())

    # Keep testing runs predictable by capping candidates.
    if len(new_releases) > remaining_slots:
        new_releases = sorted(
            new_releases,
            key=lambda r: float(r.get("market_popularity_score", 0) or 0),
            reverse=True,
        )[:remaining_slots]

    if not new_releases:
        print("Geen nieuwe releases gevonden.")
        return {"new_releases": [], "next_action": "end"}

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
    draft_orders = []

    # Prevent new-release path from mixing with old supplier/new-release data.
    if isinstance(state, dict):
        state["new_releases"] = []
        state["existing_new_releases"] = []
        state["new_releases_needing_stock"] = []
        state["purchase_order_proposals"] = []
        state["market_popular_albums"] = []
        state["uncatalogued_popular_albums"] = []
        state["market_popularity_alerts"] = []
        state.setdefault("data", {})
        state["data"]["draft_orders"] = []
    else:
        state.clear_path_data("new_releases")

    remaining_slots = _remaining_global_slots(state)
    limited_new_releases = new_releases[:remaining_slots]

    for release in limited_new_releases:
        popularity_score = float(release.get("market_popularity_score", 0) or 0)
        if popularity_score >= 85:
            suggested_qty = 10
        elif popularity_score >= 70:
            suggested_qty = 8
        else:
            suggested_qty = 5

        proposal = {
            "product_id": release['id'],
            "product_name": release['title'],
            "quantity": suggested_qty,
            "market_popularity_score": popularity_score,
            "status": "proposed"
        }
        proposals.append(proposal)

        draft_orders.append({
            "supplier_id": 1,
            "supplier_name": "Spotify Market Suggestion",
            "items": [{
                "product_id": release['id'],
                "product_name": release['title'],
                "quantity": suggested_qty,
                "unit_price": 0,
            }],
            "total_amount": 0,
            "market_popularity_score": popularity_score,
            "ai_recommendation": (
                f"Inkoop gebaseerd op Spotify marktpopulariteit score {popularity_score}."
                if popularity_score
                else "Inkoop gebaseerd op nieuwe release detectie."
            )
        })

        try:
            # Gebruik genre als category als die bestaat, anders 'Vinyl'
            category = release.get('genre') if release.get('genre') and release.get('genre') != 'Unknown' else 'Vinyl'
            added_product = db.add_product({
                "id": release['id'],
                "name": release['title'],
                "category": category,
                "supplier_id": 1,
                "artist": release.get('artist', 'Unknown'),
                "release_date": release.get('release_date')
            })
            db.add_inventory({"product_id": added_product['product_id'], "quantity_in_stock": 0, "reorder_level": 5})
        except AttributeError:
            pass  # Fallback: skip als methodes niet bestaan

    # Keep the order shape aligned with human approval node expectations.
    if draft_orders:
        if isinstance(state, dict):
            state.setdefault("data", {})
            state["data"]["draft_orders"] = draft_orders
        else:
            for order in draft_orders:
                state.add_new_release_order(order)

    print(f"{len(proposals)} ordervoorstellen aangemaakt (max {MAX_REORDER_PROPOSALS}).")
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
