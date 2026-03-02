"""
Main entry point for Procurement Vinyl Agent
Workflow: Daily Inventory Check → Find Suppliers → Create PO → Approval → Invoice Verification
"""
from agent.graph import build_procurement_graph, print_workflow_info, view_pending_orders, view_pending_invoices
from agent.nodes import ProcurementState, human_approval_node
from setup_data import setup_test_data, display_database_summary
from agent.database import ProcurementDatabase


def main():
    """Main entry point for the Procurement Vinyl Agent"""

    print("\n" + "=" * 70)
    print("🎵 PROCUREMENT VINYL AGENT - SYSTEM STARTUP")
    print("=" * 70)

    # Step 1: Initialize database with test data (only first run)
    print("\n[1/4] Checking database...")
    db = ProcurementDatabase()
    suppliers = db.get_all_suppliers()

    if not suppliers:
        print("      Database is empty. Setting up test data...")
        setup_test_data()
    else:
        print(f"      ✓ Database ready ({len(suppliers)} suppliers, {len(db.get_inventory())} products)")

    # Step 2: Display workflow info
    print("\n[2/4] Loading workflow configuration...")
    print_workflow_info()

    # Step 3: Run procurement workflow
    print("\n[3/4] Starting procurement workflow...")
    print("-" * 70)

    # Build the graph
    graph = build_procurement_graph()

    # Initialize workflow state
    state = ProcurementState(
        step="daily_inventory_check",
        status="pending",
        message="Starting daily inventory check...",
        data={},
        errors=[]
    )

    # Run the workflow
    print("\n📌 WORKFLOW EXECUTION:\n")

    try:
        # Execute the workflow
        final_state = graph.invoke(state)

        # Handle both dict and ProcurementState responses
        if isinstance(final_state, dict):
            message = final_state.get('message', 'Workflow completed')
            status = final_state.get('status', 'unknown')
            data = final_state.get('data', {})
            errors = final_state.get('errors', [])
        else:
            message = final_state.message
            status = final_state.status
            data = final_state.data
            errors = final_state.errors

        # Display results
        print(f"\n{message}")

        if status == "error":
            print(f"❌ Errors: {', '.join(errors)}")

        if data.get('awaiting_approval'):
            print("\n⏸️  WORKFLOW PAUSED - AWAITING HUMAN APPROVAL")
            print("\n" + "-" * 70)
            print("Pending Order for Approval:")
            approval_data = data['awaiting_approval']
            print(f"  Order Number: {approval_data['order_number']}")
            print(f"  Supplier: {approval_data['supplier_name']}")
            print(f"  Product: {approval_data['product_code']}")
            print(f"  Quantity: {approval_data['quantity']} units")
            print(f"  Unit Price: €{approval_data['unit_price']:.2f}")
            print(f"  Total Cost: €{approval_data['total_cost']:.2f}")
            print("\n  Status: PENDING APPROVAL")

            # Display LLM insights
            if data.get('llm_supplier_analysis'):
                print("\n" + "=" * 70)
                print("🤖 AI LEVERANCIER ANALYSE:")
                print("=" * 70)
                print(data['llm_supplier_analysis'])

            if data.get('llm_quantity_advice'):
                print("\n" + "=" * 70)
                print("🤖 AI HOEVEELHEID OPTIMALISATIE:")
                print("=" * 70)
                print(data['llm_quantity_advice'])

            if data.get('llm_approval_message'):
                print("\n" + "=" * 70)
                print("📧 AI-GEGENEREERD GOEDKEURINGSVERZOEK:")
                print("=" * 70)
                print(data['llm_approval_message'])

            print("\n" + "-" * 70)
            print("  → Manager moet deze order handmatig goedkeuren")
            print("-" * 70)

    except Exception as e:
        print(f"❌ Workflow execution error: {str(e)}")

    # Step 4: Display system status
    print("\n[4/4] System Status...")
    print("-" * 70)
    display_database_summary()

    # Show pending items
    print("\n📋 PENDING ACTIONS:")
    print("-" * 70)
    view_pending_orders()
    view_pending_invoices()

    print("\n" + "=" * 70)
    print("🚀 Procurement Vinyl Agent Ready")
    print("=" * 70)

    # Display help
    print("""
    Next Steps:
    -----------
    1. Review pending orders (above)
    2. Approve/Reject orders manually:
       from agent.nodes import human_approval_node, ProcurementState
       state = ProcurementState(...)
       human_approval_node(state, approved=True, approved_by="manager_name")
    
    3. Process invoices when received
    4. System automatically tracks supplier metrics
    """)


if __name__ == "__main__":
    main()
