"""
Simuleer prijs history en sales data voor producten.
- Genereert price_history.json en sales.json met realistische variatie.
- Past aan op basis van bestaande producten in product.json.
"""
import json
import math
import random
from datetime import datetime, timedelta

# Configuratie
PRODUCTS_FILE = "db/product.json"
PRICE_HISTORY_FILE = "db/price_history.json"
SALES_FILE = "db/sales.json"

# Simulatie parameters
DAYS = 30  # aantal dagen terug in de tijd
PRICE_FLUCTUATION = 0.07  # max 7% omhoog/omlaag per dag
MAX_SALES_EVENTS_PER_DAY = 5
CHANNELS = ["webshop", "store", "marketplace"]

# Weegfactoren voor vraagprofiel
CATEGORY_DEMAND = {
    "Pop": 1.25,
    "Rock": 1.0,
    "Progressive Rock": 0.95,
    "Hard Rock": 0.9,
    "Metal": 0.85,
    "Grunge": 0.9,
    "Jazz": 0.8,
    "Classical": 0.7,
}
WEEKDAY_MULTIPLIER = {
    0: 0.9,   # maandag
    1: 0.95,
    2: 1.0,
    3: 1.05,
    4: 1.15,  # vrijdag
    5: 1.25,  # zaterdag
    6: 1.1,   # zondag
}


def _safe_parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _demand_profile(product: dict, today: datetime) -> dict:
    """Build a per-product demand profile used by daily simulation."""
    category = product.get("category", "Unknown")
    category_factor = CATEGORY_DEMAND.get(category, 0.9)

    created_at = _safe_parse_iso(product.get("created_at"))
    days_since_creation = 365
    if created_at:
        days_since_creation = max(0, (today - created_at).days)

    # Recent catalog additions get a stronger baseline demand.
    if days_since_creation <= 14:
        recency_factor = 1.35
    elif days_since_creation <= 45:
        recency_factor = 1.18
    elif days_since_creation <= 120:
        recency_factor = 1.05
    else:
        recency_factor = 0.9

    # Product-level popularity index (0.7 - 1.6): higher means more sales events and quantity.
    popularity_index = round(random.uniform(0.7, 1.6) * category_factor * recency_factor, 3)

    # Generate 1 or 2 short hype windows for this product.
    hype_windows = []
    hype_count = 2 if random.random() < 0.35 else 1
    for _ in range(hype_count):
        start_offset = random.randint(0, max(1, DAYS - 3))
        duration = random.randint(2, 5)
        hype_windows.append({
            "start_offset": start_offset,
            "end_offset": min(DAYS, start_offset + duration),
            "multiplier": round(random.uniform(1.3, 1.9), 2),
        })

    return {
        "popularity_index": popularity_index,
        "hype_windows": hype_windows,
    }


def _hype_multiplier(day_offset: int, profile: dict) -> float:
    multiplier = 1.0
    for window in profile.get("hype_windows", []):
        if window["start_offset"] <= day_offset <= window["end_offset"]:
            multiplier = max(multiplier, float(window["multiplier"]))
    return multiplier

# Laad producten
with open(PRODUCTS_FILE, encoding="utf-8") as f:
    products = json.load(f)

# Filter alleen producten met een product_id (soms zitten er extra velden in je json)
products = [p for p in products if "product_id" in p]

# Prijs history genereren
price_history = []
for product in products:
    base_price = product.get("current_price", 30.0)
    price = base_price
    for day in range(DAYS, -1, -1):
        date = (datetime.now() - timedelta(days=day)).date()
        # Simuleer prijsfluctuatie
        price *= 1 + random.uniform(-PRICE_FLUCTUATION, PRICE_FLUCTUATION)
        price = round(max(5.0, price), 2)  # geen negatieve prijzen
        price_history.append({
            "product_id": product["product_id"],
            "date": str(date),
            "price": price
        })

# Sales genereren
sales = []
sale_id = 1
now = datetime.now()
profiles = {p["product_id"]: _demand_profile(p, now) for p in products}

for product in products:
    profile = profiles[product["product_id"]]

    for day in range(DAYS, -1, -1):
        date = now - timedelta(days=day)
        weekday_factor = WEEKDAY_MULTIPLIER[date.weekday()]
        hype_factor = _hype_multiplier(day, profile)

        # Verwachte aantal events per dag, gestuurd door popularity + kalender + hype.
        lambda_events = 1.1 * profile["popularity_index"] * weekday_factor * hype_factor
        lambda_events = max(0.1, min(lambda_events, MAX_SALES_EVENTS_PER_DAY))

        # Simpele Poisson-achtige sampling zonder externe dependencies.
        num_sales = min(
            MAX_SALES_EVENTS_PER_DAY,
            int(round(random.gauss(lambda_events, 0.8)))
        )
        num_sales = max(0, num_sales)

        # Dynamische kans op pauzedag (snellopers hebben minder vaak 0-sales dagen)
        pause_probability = max(0.08, 0.35 - (profile["popularity_index"] - 1.0) * 0.15)
        if num_sales == 0 or random.random() < pause_probability:
            continue

        for _ in range(num_sales):
            # Quantity groeit mee met populariteit en hype, met ruis.
            quantity_mean = 4.5 * profile["popularity_index"] * math.sqrt(hype_factor)
            quantity = int(round(random.gauss(quantity_mean, 2.2)))
            quantity = max(1, min(quantity, 30))

            # Webshop piekt iets vaker bij hype.
            if hype_factor > 1.0 and random.random() < 0.55:
                channel = "webshop"
            else:
                channel = random.choice(CHANNELS)

            sold_at = date.replace(
                hour=random.randint(9, 20),
                minute=random.randint(0, 59),
                second=random.randint(0, 59)
            ).isoformat() + "Z"
            sales.append({
                "sale_id": sale_id,
                "product_id": product["product_id"],
                "quantity_sold": quantity,
                "sold_at": sold_at,
                "channel": channel
            })
            sale_id += 1

# Schrijf price_history.json
with open(PRICE_HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(price_history, f, indent=2)

# Schrijf sales.json
with open(SALES_FILE, "w", encoding="utf-8") as f:
    json.dump(sales, f, indent=2)

print("Simulatie voltooid: price_history.json en sales.json zijn bijgewerkt.")
