"""
Simuleer prijs history en sales data voor producten.
- Genereert price_history.json en sales.json met realistische variatie.
- Past aan op basis van bestaande producten in product.json.
"""
import json
import random
from datetime import datetime, timedelta

# Configuratie
PRODUCTS_FILE = "db/product.json"
PRICE_HISTORY_FILE = "db/price_history.json"
SALES_FILE = "db/sales.json"

# Simulatie parameters
DAYS = 30  # aantal dagen terug in de tijd
PRICE_FLUCTUATION = 0.07  # max 7% omhoog/omlaag per dag
SALES_PER_DAY = (0, 3)  # min/max sales per product per dag
CHANNELS = ["webshop", "store", "marketplace"]

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
for product in products:
    for day in range(DAYS, -1, -1):
        date = datetime.now() - timedelta(days=day)
        # 30% kans op een pauzedag (geen sales voor dit product op deze dag)
        if random.random() < 0.3:
            continue
        num_sales = random.randint(*SALES_PER_DAY)
        for _ in range(num_sales):
            quantity = random.randint(1, 25)
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
