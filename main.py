"""
Main entry point - generates test data as JSON
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_data(num_items=100):
    """Generate all test data without external dependencies"""
    data = {
        'PRODUCT': [],
        'SUPPLIER': [],
        'INVENTORY': [],
        'PURCHASE_ORDER': [],
        'PURCHASE_ORDER_ITEM': [],
        'PRICE_HISTORY': [],
        'SUPPLIER_PERFORMANCE': []
    }

    # Sample data for generation
    product_names = ['Vinyl', 'Record', 'Album', 'Turntable', 'Speaker', 'Amplifier', 'Cable', 'Needle', 'Mat', 'Cleaner']
    product_adjectives = ['Premium', 'Classic', 'Vintage', 'Professional', 'Deluxe', 'Ultra', 'Pro', 'Elite', 'Standard', 'Basic']
    categories = ['Vinyl Records', 'Turntables', 'Speakers', 'Accessories', 'Cleaning Supplies']

    company_names = ['SoundWave Inc', 'Vinyl Masters', 'Audio Tech', 'Record House', 'Music Pro', 'Turntable Co', 'Speaker Systems', 'Audio Solutions', 'Vinyl Vault', 'Music Store']

    statuses = ['Pending', 'Confirmed', 'Shipped', 'Delivered', 'Cancelled']

    # PRODUCT
    for i in range(1, num_items + 1):
        data['PRODUCT'].append({
            'product_id': i,
            'name': f"{random.choice(product_adjectives)} {random.choice(product_names)} {i}",
            'description': f'High quality product for vinyl enthusiasts. SKU: SKU-{i:05d}',
            'sku': f"SKU-{i:05d}",
            'category': random.choice(categories),
            'current_price': round(random.uniform(10, 500), 2),
            'created_at': (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat()
        })

    # SUPPLIER
    for i in range(1, num_items + 1):
        data['SUPPLIER'].append({
            'supplier_id': i,
            'name': f"{random.choice(company_names)} {i}",
            'contact_email': f"contact{i}@supplier{i}.com",
            'phone': f"+31 {random.randint(100, 999)} {random.randint(100000, 999999)}",
            'address': f"Street {i}, {random.randint(1000, 9999)} City, Netherlands",
            'created_at': (datetime.now() - timedelta(days=random.randint(1, 730))).isoformat()
        })

    # INVENTORY (1:1 with PRODUCT)
    for i in range(1, num_items + 1):
        data['INVENTORY'].append({
            'inventory_id': i,
            'product_id': i,
            'quantity_in_stock': random.randint(0, 1000),
            'reorder_level': random.randint(5, 50),
            'last_updated': (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
        })

    # PURCHASE_ORDER
    for i in range(1, num_items + 1):
        order_date = datetime.now() - timedelta(days=random.randint(1, 180))
        expected_delivery = order_date + timedelta(days=random.randint(5, 30))
        actual_delivery = expected_delivery + timedelta(days=random.randint(-5, 10)) if random.random() > 0.2 else None

        data['PURCHASE_ORDER'].append({
            'purchase_order_id': i,
            'supplier_id': random.randint(1, num_items),
            'order_date': order_date.isoformat(),
            'expected_delivery_date': expected_delivery.isoformat(),
            'actual_delivery_date': actual_delivery.isoformat() if actual_delivery else None,
            'status': random.choice(statuses),
            'total_amount': round(random.uniform(100, 10000), 2)
        })

    # PURCHASE_ORDER_ITEM
    item_id = 1
    for po_id in range(1, num_items + 1):
        num_items_in_order = random.randint(2, 5)
        for _ in range(num_items_in_order):
            data['PURCHASE_ORDER_ITEM'].append({
                'purchase_order_item_id': item_id,
                'purchase_order_id': po_id,
                'product_id': random.randint(1, num_items),
                'quantity': random.randint(1, 100),
                'unit_price': round(random.uniform(10, 500), 2)
            })
            item_id += 1

    # PRICE_HISTORY
    price_id = 1
    for product_id in range(1, num_items + 1):
        num_prices = random.randint(1, 3)
        for j in range(num_prices):
            start_date = datetime.now() - timedelta(days=random.randint(1, 365))
            end_date = start_date + timedelta(days=random.randint(30, 180)) if j < num_prices - 1 else None

            data['PRICE_HISTORY'].append({
                'price_history_id': price_id,
                'product_id': product_id,
                'price': round(random.uniform(10, 500), 2),
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat() if end_date else None
            })
            price_id += 1

    # SUPPLIER_PERFORMANCE
    for i in range(1, num_items + 1):
        total_orders = random.randint(1, 50)
        late_deliveries = random.randint(0, min(total_orders, 10))
        reliability = round(100 - (late_deliveries / total_orders * 100), 2) if total_orders > 0 else 100

        data['SUPPLIER_PERFORMANCE'].append({
            'performance_id': i,
            'supplier_id': i,
            'total_orders': total_orders,
            'late_deliveries': late_deliveries,
            'reliability_score': reliability,
            'evaluation_date': (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
        })

    return data


if __name__ == "__main__":
    print("Generating test data...")
    data = generate_data(100)

    # Save to JSON in db directory
    db_dir = Path(__file__).parent / "db"
    db_dir.mkdir(exist_ok=True)

    output_file = db_dir / "inventory.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    # Print summary
    print(f"\n✓ Data generated successfully!")
    print(f"\nSummary:")
    for table_name, records in data.items():
        print(f"  {table_name}: {len(records)} records")

    print(f"\n✓ Saved to: {output_file}")

