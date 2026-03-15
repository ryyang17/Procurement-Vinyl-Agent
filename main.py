import uuid

from agent.agent import create_procurement_workflow
from agent.procurement_data import ProcurementDatabase
from agent.utils.memory import get_all_decisions
from agent.utils.state import ProcurementState
from agent.utils.nodes.new_release_nodes import detect_new_releases_node


db = ProcurementDatabase()


def demonstrate_new_release_detection():
    """Demonstrate the new release detection functionality (Spotify)"""
    print("\n🎵 === NEW RELEASE DETECTION ===\n")
    state = ProcurementState()
    result = detect_new_releases_node(state)
    new_releases = result.get("new_releases", [])
    if new_releases:
        print(f"📀 Found {len(new_releases)} new releases:")
        for release in new_releases:
            print(f"   • {release['title']} by {release.get('artist', '-')}")
    else:
        print("Geen nieuwe releases gevonden.")
    print("\n🎯 New release detection complete!")
    return new_releases


def run_procurement_workflow() -> None:
    """Run the procurement workflow with human approval step."""
    print("\n🔄 VINYL PROCUREMENT AGENT WORKFLOW\n")
    workflow = create_procurement_workflow()
    thread_id = str(uuid.uuid4())[:8].upper()
    state = ProcurementState(thread_id=thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    # Start workflow
    result = workflow.invoke(state, config=config)
    if isinstance(result, dict):
        result = ProcurementState(**result)

    # Show what needs to be ordered
    proposals = result.data.get("reorder_proposals", [])
    if proposals:
        print(f"📦 Te bestellen producten: {[p['product_name'] for p in proposals]}")
    else:
        print("✅ Alles op voorraad. Geen actie nodig.")
        return

    # Show supplier selections
    selections = result.data.get("supplier_selections", [])
    if selections:
        print("\n🏪 Geselecteerde leveranciers:")
        for i, sel in enumerate(selections, 1):
            s = sel["selected_supplier"]
            print(f"  {i}. {sel['product_name']} bij {s['supplier_name']} voor €{s['price_per_unit']:.2f}")

    # Handle human approval
    draft_orders = result.data.get("draft_orders", [])
    if draft_orders and result.step == "awaiting_human_input":
        print("\n📋 CONCEPTBESTELLINGEN VOOR GOEDKEURING:\n")

        for idx, order in enumerate(draft_orders, 1):
            print(f"Concept #{idx}")
            print(f"  Leverancier: {order.get('supplier_name', '-')}")
            print(f"  Levertijd: {order.get('lead_time_days', '-')} dagen")
            print(f"  Kwaliteit: {order.get('quality_rating', '-')}/10")
            print("  Producten:")
            for item in order.get("items", []):
                print(f"    • {item.get('product_name', '-')} x {item.get('quantity', '-')} @ €{item.get('unit_price', '-')}")
            print(f"  💰 Totaal: €{order.get('total_amount', '-')}")

            # Show AI recommendation
            ai_rec = order.get("ai_recommendation", "Geen AI-analyse beschikbaar")
            ai_text = ai_rec if isinstance(ai_rec, str) else str(ai_rec)
            print(f"  🤖 AI Aanbeveling: {ai_text}")
            print()

        print("🔍 Goedkeuren? Opties:")
        print("  • 'all' - Alles goedkeuren")
        print("  • '1,2,3' - Specifieke orders goedkeuren")
        print("  • 'none' - Alles afwijzen")
        print("  • 'reject:1,2' - Specifieke orders afwijzen")

        try:
            user_input = input("\n👤 Uw beslissing: ").strip().lower()
        except EOFError:
            print("❌ Geen invoer. Workflow gestopt.")
            return

        approved = []
        rejected = {}

        # Process user input
        if user_input == "all":
            approved = list(range(len(draft_orders)))
        elif user_input == "none":
            print("📝 Reden voor afwijzing van alle orders? (Enter om over te slaan)")
            try:
                reason = input().strip() or "Alle orders afgewezen door manager"
            except EOFError:
                reason = "Alle orders afgewezen door manager"
            rejected = {i: reason for i in range(len(draft_orders))}
        elif user_input.startswith("reject:"):
            parts = user_input[7:].split(",")
            for part in parts:
                try:
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(draft_orders):
                        rejected[idx] = "Afgewezen door manager"
                except ValueError:
                    continue
        else:
            try:
                approved = [
                    int(x.strip()) - 1
                    for x in user_input.split(",")
                    if x.strip().isdigit() and 0 < int(x.strip()) <= len(draft_orders)
                ]
            except Exception:
                print("❌ Ongeldige invoer. Workflow gestopt.")
                return

        # Set approval data and continue workflow
        result.approved_orders = approved
        result.rejection_reasons = rejected
        result.approved_by = "user"
        result.approval_decision = "approved"

        # Process approval
        result = workflow.invoke(result, config=config)
        if isinstance(result, dict):
            result = ProcurementState(**result)

    # Show results
    created = result.data.get("created_orders", [])
    if created:
        print(f"\n✅ Bestellingen aangemaakt: {[f'#{o['order_id']}' for o in created]}")
    else:
        print("\n❌ Geen bestellingen aangemaakt.")


def show_pending_orders() -> None:
    """Show pending purchase orders awaiting approval."""
    pending = db.get_pending_purchase_orders()
    if not pending:
        print("\n✅ Geen openstaande bestellingen.")
        return

    print(f"\n📋 OPENSTAANDE BESTELLINGEN ({len(pending)})\n")
    for order in pending:
        print(f"Order #{order['purchase_order_id']} - {order['supplier_name']}")
        print(f"  💰 Totaal: €{order['total_amount']:.2f}")
        print(f"  📅 Verwacht: {order['expected_delivery_date'] or 'TBD'}")
        print(f"  📦 Items: {len(order['items'])}")
        print()


def show_decision_history(limit: int = 5) -> None:
    """Show recent procurement decisions."""
    decisions = get_all_decisions(limit=limit)
    if not decisions:
        print("\n❌ Geen recente beslissingen.")
        return

    print(f"\n📜 RECENTE BESLISSINGEN (laatste {limit})\n")
    for decision in reversed(decisions):
        timestamp = decision['timestamp'][:16].replace('T', ' ')
        print(f"{timestamp} - {decision['type']}")
        if decision.get("supplier_name"):
            print(f"  🏪 {decision['supplier_name']}")
        if decision.get("reason"):
            print(f"  📝 {decision['reason']}")
        if decision.get("po_id"):
            print(f"  📋 Order #{decision['po_id']}")
        print()


def interactive_menu() -> None:
    """Main interactive menu with essential procurement workflow options."""
    while True:
        print("\n" + "=" * 60)
        print("🎵 VINYL PROCUREMENT AGENT")
        print("=" * 60)

        print("1. ▶️  Start Procurement Workflow")
        print("2. 🎵 New Release Detection")
        print("4. 📋 Bekijk Openstaande Bestellingen")
        print("5. 📜 Bekijk Recente Beslissingen")
        print("0. 🚪 Afsluiten")

        try:
            choice = input(f"\n👤 Kies optie (0-5): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Tot ziens!")
            break

        if choice == "1":
            run_procurement_workflow()
        elif choice == "2":
            demonstrate_new_release_detection()
        elif choice == "4":
            show_pending_orders()
        elif choice == "5":
            try:
                limit_input = input("Aantal beslissingen (standaard 5): ").strip()
                limit = int(limit_input) if limit_input else 5
                show_decision_history(limit)
            except ValueError:
                print("❌ Ongeldig aantal, gebruik standaard 5")
                show_decision_history(5)
        elif choice == "0":
            print("\n👋 Tot ziens!")
            break
        else:
            print("❌ Ongeldige keuze, probeer opnieuw")


if __name__ == "__main__":
    interactive_menu()
