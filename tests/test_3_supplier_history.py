import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent.utils.memory import get_supplier_history, get_supplier_summary
from agent.procurement_data import ProcurementDatabase

def main():
    print("\n" + "="*60)
    print("TEST 3: SUPPLIER HISTORY QUERIES")
    print("="*60)

    db = ProcurementDatabase()

    # STAP 1: Get supplier
    print("\n[STAP 1] Select supplier")
    suppliers = db.get_suppliers()
    test_supplier = suppliers[0]

    print(f"✓ Selected: {test_supplier['name']} (ID: {test_supplier['supplier_id']})")

    # STAP 2: Get history
    print("\n[STAP 2] Get supplier history (last 30 days)")
    history = get_supplier_history(test_supplier['supplier_id'], days=30)

    print(f"✓ Found {len(history)} decisions:")
    if history:
        for i, event in enumerate(history, 1):
            decision_type = "✓ APPROVED" if event['type'] == 'supplier_approved' else "✗ REJECTED"
            reason = event['reason'][:40] if event['reason'] else "No reason"
            print(f"  {i}. {decision_type} - {reason}...")
    else:
        print("  (No history yet)")

    # STAP 3: Get summary
    print("\n[STAP 3] Get supplier summary")
    summary = get_supplier_summary(test_supplier['supplier_id'])

    print(f"✓ Summary:")
    print(f"  Approvals: {summary['approval_count']}")
    print(f"  Rejections: {summary['rejection_count']}")

    total = summary['approval_count'] + summary['rejection_count']
    if total > 0:
        approval_rate = summary['approval_count'] / total * 100
        print(f"  Approval rate: {approval_rate:.1f}%")

    print(f"  Last decision: {summary['last_decision']}")

    if summary['last_rejection_reason']:
        print(f"  Last rejection reason: {summary['last_rejection_reason'][:40]}...")

    # STAP 4: Verify
    print("\n[STAP 4] Verification")

    # Check that summary counts match history length
    approval_in_history = sum(1 for e in history if e['type'] == 'supplier_approved')
    rejection_in_history = sum(1 for e in history if e['type'] == 'supplier_rejected')

    counts_match = (
        summary['approval_count'] == approval_in_history and
        summary['rejection_count'] == rejection_in_history
    )

    if counts_match:
        print("✓ Summary counts match history")
    else:
        print(f"⚠️ Count mismatch:")
        print(f"  Summary: {summary['approval_count']} approvals, {summary['rejection_count']} rejections")
        print(f"  History: {approval_in_history} approvals, {rejection_in_history} rejections")

    print("\n" + "="*60)
    print("✓ TEST 3 PASSED")
    print("="*60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


