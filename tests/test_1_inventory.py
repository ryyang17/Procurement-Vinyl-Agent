import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent.utils.memory import log_decision, _ensure_memory_file_exists, get_all_decisions
from agent.procurement_data import ProcurementDatabase
import json

def main():
    print("\n" + "="*60)
    print("TEST 1: INVENTORY SHORTAGE")
    print("="*60)

    db = ProcurementDatabase()
    _ensure_memory_file_exists()

    # STAP 1: Get product met lage voorraad
    print("\n[STAP 1] Find product met lage voorraad")
    products = db.get_products()
    inventory = db.get_inventory()
    low_stock_product = None
    low_stock_inventory = None

    for inv in inventory:
        if inv['quantity_in_stock'] < inv['reorder_level'] * 2:
            product = next((p for p in products if p['product_id'] == inv['product_id']), None)
            if product:
                low_stock_product = product
                low_stock_inventory = inv
                break

    if not low_stock_product:
        print("❌ Geen product met lage voorraad gevonden")
        return False

    print(f"✓ Found: {low_stock_product['name']}")
    print(f"  Current: {low_stock_inventory['quantity_in_stock']} units")
    print(f"  Reorder level: {low_stock_inventory['reorder_level']} units")

    # STAP 2: Find suppliers
    print("\n[STAP 2] Find best supplier")
    suppliers = db.get_suppliers_for_product(low_stock_product['product_id'])

    if not suppliers:
        print("❌ Geen suppliers gevonden")
        return False

    best_supplier = min(suppliers, key=lambda x: x['price_per_unit'])
    print(f"✓ Best supplier: {best_supplier['supplier_name']}")
    print(f"  Price: €{best_supplier['price_per_unit']:.2f}/unit")
    print(f"  Lead time: {best_supplier['lead_time_days']} days")

    # STAP 3: Log approval decision
    print("\n[STAP 3] Log approval decision")
    decision = log_decision(
        decision_type='supplier_approved',
        supplier_id=best_supplier['supplier_id'],
        supplier_name=best_supplier['supplier_name'],
        reason=f"Low stock detected: {low_stock_inventory['quantity_in_stock']} < {low_stock_inventory['reorder_level'] * 2}. Best price available.",
        context={
            'product_id': low_stock_product['product_id'],
            'product_name': low_stock_product['name'],
            'current_stock': low_stock_inventory['quantity_in_stock'],
            'reorder_qty': 500,
            'scenario': 'inventory_shortage'
        },
        actor='procurement_agent'
    )

    print(f"✓ Decision logged")
    print(f"  Timestamp: {decision['timestamp']}")
    print(f"  Type: {decision['type']}")

    # STAP 4: Verify in memory
    print("\n[STAP 4] Verify memory persistence")
    all_decisions = get_all_decisions(limit=10)

    our_decision = None
    for d in all_decisions:
        if (d['supplier_id'] == best_supplier['supplier_id'] and
            d['type'] == 'supplier_approved'):
            our_decision = d
            break

    if not our_decision:
        print("❌ Decision NOT found in memory!")
        return False

    print("✓ Decision found in memory!")
    print(f"\nDecision details:")
    print(json.dumps(our_decision, indent=2, ensure_ascii=False))

    # STAP 5: Check raw file
    print("\n[STAP 5] Check raw decision_log.json file")
    memory_path = Path(__file__).parent.parent / "db" / "decision_log.json"
    with open(memory_path) as f:
        file_content = json.load(f)

    print(f"✓ File contains {len(file_content)} total decisions")
    print(f"✓ Last 3 decisions:")
    for i, d in enumerate(file_content[-3:], 1):
        print(f"  {i}. {d['type']} - {d['supplier_name']} [{d['timestamp'][:10]}]")

    print("\n" + "="*60)
    print("✓ TEST 1 PASSED")
    print("="*60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
