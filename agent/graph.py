"""
LangGraph Orchestration Layer - Defines the procurement workflows
"""
from dotenv import load_dotenv
from langchain_core.runnables.graph import Graph

load_dotenv()

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.nodes import (
    ProcurementState,
    daily_inventory_check_node,
    find_suppliers_node,
    create_purchase_order_node,
    human_approval_node,
    verify_invoice_node,
    update_supplier_history_node,
    get_pending_approvals,
    get_pending_invoices,
    should_generate_proposals,
    has_invoice_discrepancy
)

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview",
    temperature=1,  # Lower = more deterministic for procurement decisions
    max_tokens=1000
)

# System prompt for procurement agent
PROCUREMENT_AGENT_PROMPT = """Je bent een AI Procurement Agent gespecialiseerd in vinyl producten.

Je taken:
1. Analyseer voorraadniveaus en genereer inkoopvoorstellen
2. Evalueer leveranciers op prijs, levertijd, betrouwbaarheid en historie
3. Optimaliseer bestelhoeveelheden gebaseerd op voorraad patronen
4. Formuleer duidelijke goedkeuringsverzoeken voor managers
5. Detecteer afwijkingen in facturen

Antwoord altijd:
- Professioneel en beknopt
- Met duidelijke motivering
- In het Nederlands
- Met concrete cijfers en data
"""


def build_procurement_graph():
    """
    Build the LangGraph workflow for procurement

    Automated Workflow Steps (R1-R8):
    1. Daily Inventory Check (R1) → Find items below threshold
    2. If items need reordering:
       3. Find Suppliers (R4-R5) → Compare up to 3 suppliers
       4. Create Purchase Order (R6-R8) → Awaiting manual approval

    Manual Steps (called separately):
    - Human Approval (R6-R8) → Approve/Reject orders
    - Invoice Verification (R9-R10) → Check invoice discrepancies
    - Supplier History (R11) → Track performance metrics
    """

    # Create the state graph
    workflow = StateGraph(ProcurementState)

    # ==================== NODES ====================

    # Node 1: Daily inventory check
    workflow.add_node("daily_inventory_check", daily_inventory_check_node)

    # Node 2: Find suppliers
    workflow.add_node("find_suppliers", find_suppliers_node)

    # Node 3: Create purchase order (awaiting approval)
    workflow.add_node("create_purchase_order", create_purchase_order_node)

    # ==================== EDGES (CONTROL FLOW) ====================

    # Start with daily inventory check
    workflow.set_entry_point("daily_inventory_check")

    # Route: If inventory is sufficient, end. Otherwise, find suppliers
    workflow.add_conditional_edges(
        "daily_inventory_check",
        lambda state: "find_suppliers" if state.status == "processing" else END,
        {
            "find_suppliers": "find_suppliers",
            END: END
        }
    )

    # Find suppliers -> Create purchase order
    workflow.add_edge("find_suppliers", "create_purchase_order")

    # Create purchase order -> END (awaiting manual approval)
    workflow.add_edge("create_purchase_order", END)

    # Compile the graph
    return workflow.compile()

from IPython.display import Image, display

display(Image(Graph.get_graph().dram.mermaid_png()))

# ==================== GRAPH VISUALIZATION ====================

def print_workflow_info():
    """Print workflow structure info"""
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║     PROCUREMENT VINYL AGENT - WORKFLOW ORCHESTRATION           ║
    ╠════════════════════════════════════════════════════════════════╣
    ║                                                                ║
    ║ [1] Daily Inventory Check (R1-R3)                            ║
    ║     ├─ Check all inventory items                            ║
    ║     ├─ Generate proposals for low stock                     ║
    ║     └─ Route to supplier finding if needed                  ║
    ║        │                                                     ║
    ║        ▼                                                     ║
    ║ [2] Find Suppliers (R4-R5)                                 ║
    ║     ├─ Query suppliers offering product                    ║
    ║     ├─ Compare up to 3 options                             ║
    ║     └─ Select best based on price+lead time                ║
    ║        │                                                     ║
    ║        ▼                                                     ║
    ║ [3] Create Purchase Order (R6-R8)                         ║
    ║     ├─ Generate order awaiting approval                    ║
    ║     ├─ Show: supplier, qty, total cost                     ║
    ║     └─ Status: pending_approval                            ║
    ║        │                                                     ║
    ║        ▼                                                     ║
    ║ [4] Human Approval (R6-R8)                                ║
    ║     ├─ Manual approval/rejection needed                    ║
    ║     ├─ Update order status                                 ║
    ║     └─ Route to invoice verification                       ║
    ║        │                                                     ║
    ║        ▼                                                     ║
    ║ [5] Invoice Verification (R9-R10)                         ║
    ║     ├─ Compare invoice vs PO                               ║
    ║     ├─ Check price & quantity match                        ║
    ║     └─ Alert on discrepancies                              ║
    ║        │                                                     ║
    ║        ▼                                                     ║
    ║ [6] Supplier History Tracking (R11)                       ║
    ║     ├─ Update last price paid                              ║
    ║     ├─ Record late deliveries                              ║
    ║     └─ Update quality metrics                              ║
    ║        │                                                     ║
    ║        ▼                                                     ║
    ║      [END]                                                   ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝
    """)


# ==================== HELPER FUNCTIONS ====================

def view_pending_orders():
    """View all orders pending human approval"""
    pending = get_pending_approvals()
    print(f"\n📋 Pending Orders ({pending['count']}):")
    for order in pending['orders']:
        print(f"  • {order['order_number']}: {order['supplier_name']} - {order['quantity']} units @ €{order['unit_price']}")


def view_pending_invoices():
    """View all invoices with discrepancies"""
    pending = get_pending_invoices()
    print(f"\n⚠️  Invoices Awaiting Verification ({pending['count']}):")
    for invoice in pending['invoices']:
        print(f"  • {invoice['invoice_number']}: {invoice['discrepancy_type']}")
        print(f"    {invoice['discrepancy_message']}")


if __name__ == "__main__":
    print_workflow_info()


