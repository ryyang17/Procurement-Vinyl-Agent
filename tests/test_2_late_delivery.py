import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from agent.utils.memory import log_decision, update_supplier_performance_on_rejection
from agent.procurement_data import ProcurementDatabase

def main():
    print("\n" + "="*60)
    print("TEST 2: LATE DELIVERY & METRICS UPDATE")
    print("="*60)

    db = ProcurementDatabase()

    # STAP 1: Get supplier
    print("\n[STAP 1] Select supplier for testing")
    suppliers = db.get_suppliers()
    test_supplier = suppliers[0]

    print(f"✓ Selected: {test_supplier['name']} (ID: {test_supplier['supplier_id']})")

    # STAP 2: Check performance BEFORE
    print("\n[STAP 2] Check performance metrics BEFORE")
    perf_path = Path(__file__).parent.parent / "db" / "supplier_performance.json"

    with open(perf_path) as f:
        perfs_before = json.load(f)

    supplier_perf_before = next(
        (p for p in perfs_before if p['supplier_id'] == test_supplier['supplier_id']),
        None
    )

    if supplier_perf_before:
        print(f"✓ Before:")
        print(f"  Reliability score: {supplier_perf_before.get('reliability_score', 1.0):.3f}")
        print(f"  Late deliveries: {supplier_perf_before.get('late_deliveries', 0)}")
        score_before = supplier_perf_before.get('reliability_score', 1.0)
        late_before = supplier_perf_before.get('late_deliveries', 0)
    else:
        print(f"⚠️ No performance record found for supplier")
        score_before = 1.0
        late_before = 0

    # STAP 3: Log rejection (late delivery)
    print("\n[STAP 3] Log rejection with late delivery reason")
    decision = log_decision(
        decision_type='supplier_rejected',
        supplier_id=test_supplier['supplier_id'],
        supplier_name=test_supplier['name'],
        reason='Vertraging in levering - bestelling was 5 dagen te laat bezorgd',
        context={
            'order_id': 'PO-2026-001',
            'expected_date': '2026-03-10',
            'actual_date': '2026-03-15',
            'delay_days': 5,
            'scenario': 'late_delivery'
        },
        actor='system'
    )

    print(f"✓ Rejection logged")
    print(f"  Timestamp: {decision['timestamp']}")
    print(f"  Reason: {decision['reason']}")

    # STAP 4: Update performance metrics
    print("\n[STAP 4] Update performance metrics")
    update_supplier_performance_on_rejection(
        supplier_id=test_supplier['supplier_id'],
        rejection_reason='Vertraging in levering - bestelling was 5 dagen te laat bezorgd'
    )
    print(f"✓ Performance metrics updated")

    # STAP 5: Check performance AFTER
    print("\n[STAP 5] Check performance metrics AFTER")
    with open(perf_path) as f:
        perfs_after = json.load(f)

    supplier_perf_after = next(
        (p for p in perfs_after if p['supplier_id'] == test_supplier['supplier_id']),
        None
    )

    if not supplier_perf_after:
        print(f"❌ No performance record found after update")
        return False

    print(f"✓ After:")
    print(f"  Reliability score: {supplier_perf_after.get('reliability_score', 1.0):.3f}")
    print(f"  Late deliveries: {supplier_perf_after.get('late_deliveries', 0)}")

    score_after = supplier_perf_after.get('reliability_score', 1.0)
    late_after = supplier_perf_after.get('late_deliveries', 0)

    # STAP 6: Verify the changes
    print(f"\n[STAP 6] Verification")
    score_decreased = score_after < score_before
    count_increased = late_after > late_before

    print(f"✓ Score decreased: {score_decreased} ({score_before:.3f} -> {score_after:.3f})")
    print(f"✓ Late count increased: {count_increased} ({late_before} -> {late_after})")

    if score_decreased and count_increased:
        print("\n" + "="*60)
        print("✓ TEST 2 PASSED")
        print("="*60)
        return True
    else:
        print("\n" + "="*60)
        print("❌ TEST 2 FAILED - metrics not updated correctly")
        print("="*60)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)



