from agent.graph import create_procurement_workflow
from agent.models import ProcurementState
from agent.nodes.approval_nodes import process_approval_node

def print_separator():
    print("\n" + "="*80 + "\n")

def display_reorder_proposals(state):
    """Display reorder proposals from inventory check"""
    data = state if isinstance(state, dict) else state.data
    proposals = data.get('reorder_proposals', [])
    if not proposals:
        return

    print("VOORRAAD CONTROLE RESULTATEN")
    print_separator()
    print(f"Gevonden: {len(proposals)} producten met lage voorraad\n")

    for i, proposal in enumerate(proposals, 1):
        print(f"{i}. {proposal['product_name']} ({proposal['product_code']})")
        print(f"   Huidige voorraad: {proposal['current_qty']} stuks")
        print(f"   Minimum niveau: {proposal['min_threshold']} stuks")
        print(f"   Voorgestelde bestelhoeveelheid: {proposal['reorder_qty']} stuks")
        print()

def display_supplier_selections(state):
    """Display selected suppliers"""
    data = state if isinstance(state, dict) else state.data
    selections = data.get('supplier_selections', [])
    if not selections:
        return

    print("LEVERANCIER SELECTIE")
    print_separator()

    for i, sel in enumerate(selections, 1):
        supplier = sel['selected_supplier']
        print(f"{i}. Product: {sel['product_name']} ({sel['product_code']})")
        print(f"   Hoeveelheid: {sel['reorder_qty']} stuks")
        print(f"   Geselecteerde leverancier: {supplier['supplier_name']}")
        print(f"   Prijs per unit: €{supplier['price_per_unit']:.2f}")
        print(f"   Totaal: €{sel['reorder_qty'] * supplier['price_per_unit']:.2f}")
        print(f"   Levertijd: {supplier['lead_time_days']} dagen")
        print(f"   Kwaliteit: {supplier['quality_rating']}/10")
        print(f"\n   AI Aanbeveling:")
        for line in sel['ai_recommendation'].split('\n'):
            print(f"   {line}")
        print()

def display_draft_orders(state) -> list:
    """Display draft orders for approval and get user input"""
    data = state if isinstance(state, dict) else state.data
    draft_orders = data.get('draft_orders', [])
    if not draft_orders:
        return []

    print("CONCEPTBESTELLINGEN VOOR GOEDKEURING")
    print_separator()

    for i, order in enumerate(draft_orders):
        print(f"\n{'='*80}")
        print(f"BESTELLING #{i+1}")
        print(f"{'='*80}\n")
        print(f"Leverancier: {order['supplier_name']}")
        print(f"Levertijd: {order['lead_time_days']} dagen")
        print(f"Kwaliteitsbeoordeling: {order['quality_rating']}/10")
        print(f"\nProducten:")

        for item in order['items']:
            subtotal = item['quantity'] * item['unit_price']
            print(f"  - {item['product_name']} ({item['product_code']})")
            print(f"    {item['quantity']} x €{item['unit_price']:.2f} = €{subtotal:.2f}")

        print(f"\nTOTAAL: EUR {order['total_amount']:.2f}")
        print(f"\nAI AANBEVELING:")
        for line in order['ai_recommendation'].split('\n'):
            print(f"   {line}")
        print()

    # Get user approval
    print_separator()
    print("Welke bestellingen wil je goedkeuren?")
    print("Voer de nummers in, gescheiden door komma's (bijv: 1,2,3)")
    print("Of voer 'all' in om alles goed te keuren, of 'none' om alles te annuleren")
    print()

    user_input = input("Jouw keuze: ").strip().lower()

    if user_input == 'none':
        return []
    elif user_input == 'all':
        return list(range(len(draft_orders)))
    else:
        try:
            # Parse comma-separated numbers
            approved = [int(x.strip()) - 1 for x in user_input.split(',')]
            # Filter valid indices
            approved = [idx for idx in approved if 0 <= idx < len(draft_orders)]
            return approved
        except:
            print("Ongeldige invoer. Geen bestellingen goedgekeurd.")
            return []

def display_final_results(state):
    """Display final results"""
    data = state if isinstance(state, dict) else state.data
    created_orders = data.get('created_orders', [])

    print_separator()
    print("VOLTOOIDE BESTELLINGEN")
    print_separator()

    if not created_orders:
        print("Geen bestellingen aangemaakt.")
        return

    print(f"Succesvol {len(created_orders)} bestelling(en) aangemaakt:\n")

    total_spent = 0
    for order in created_orders:
        print(f"Order #{order['order_id']}")
        print(f"   Leverancier: {order['supplier_name']}")
        print(f"   Totaalbedrag: EUR {order['total_amount']:.2f}")
        print()
        total_spent += order['total_amount']

    print(f"TOTAAL BESTEED: EUR {total_spent:.2f}")
    print()

def main():
    """Main function to run the procurement agent"""
    print("\n" + "="*80)
    print(" "*20 + "VINYL PROCUREMENT AGENT")
    print("="*80 + "\n")

    # Create workflow
    print("Workflow wordt geïnitialiseerd...")
    workflow = create_procurement_workflow()

    # Initialize state
    initial_state = ProcurementState()

    print("Agent start met dagelijkse voorraad controle...\n")

    # Run workflow until it needs human input
    result = workflow.invoke(initial_state)

    # Display results step by step
    print_separator()
    display_reorder_proposals(result)

    # Handle both dict and ProcurementState
    status = result.get('status') if isinstance(result, dict) else result.status
    step = result.get('step') if isinstance(result, dict) else result.step

    if status == 'ok':
        print("Alle voorraden zijn op niveau. Geen actie nodig.")
        return

    print_separator()
    display_supplier_selections(result)

    print_separator()

    # If we have draft orders, get approval
    if step == "awaiting_human_input":
        approved_orders = display_draft_orders(result)

        if approved_orders:
            # Process approvals
            print("\nBestellingen worden verwerkt...")
            approved_by = input("Je naam (voor goedkeuring): ").strip() or "manager"

            result = process_approval_node(result, approved_orders, approved_by)

            # Display final results
            display_final_results(result)
        else:
            print("\nGeen bestellingen goedgekeurd. Proces geannuleerd.")

    print_separator()
    print("Agent voltooid.")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
