"""
LangGraph Orchestration Layer - Defines the procurement workflows with memory support
"""
from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
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
    model="gemini-2.0-flash-exp",
    temperature=0.3,  # Lower = more deterministic for procurement decisions
    max_tokens=1500
)

# Initialize memory checkpointer for LangGraph state persistence
memory = MemorySaver()

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
    Build the LangGraph workflow for procurement with memory support

    Automated Workflow Steps (R1-R8):
    1. Daily Inventory Check (R1) → Find items below threshold with AI analysis
    2. If items need reordering:
       3. Find Suppliers (R4-R5) → Compare up to 3 suppliers with AI recommendations
       4. Create Purchase Order (R6-R8) → Awaiting manual approval with AI insights

    Manual Steps (called separately):
    - Human Approval (R6-R8) → Approve/Reject orders
    - Invoice Verification (R9-R10) → Check invoice discrepancies
    - Supplier History (R11) → Track performance metrics

    Memory: All LLM decisions and reasoning are stored for future context
    """

    # Create the state graph
    workflow = StateGraph(ProcurementState)

    # ==================== NODES ====================

    # Node 1: Daily inventory check with AI analysis
    workflow.add_node("daily_inventory_check", daily_inventory_check_node)

    # Node 2: Find suppliers with AI recommendations
    workflow.add_node("find_suppliers", find_suppliers_node)

    # Node 3: Create purchase order with AI approval message
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

    # Compile the graph with memory persistence
    return workflow.compile(checkpointer=memory)


# ==================== GRAPH VISUALIZATION ====================

def print_workflow_info():
    """Print workflow structure info"""
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║   PROCUREMENT VINYL AGENT - AI-ENHANCED WORKFLOW 🤖            ║
    ╠════════════════════════════════════════════════════════════════╣
    ║                                                                ║
    ║ [1] Daily Inventory Check (R1-R3) + AI Analysis              ║
    ║     ├─ Check inventory with sales velocity tracking           ║
    ║     ├─ AI analyzes urgency & optimal reorder quantity        ║
    ║     ├─ Considers: sales trend, lead time, stockout risk      ║
    ║     └─ Generate intelligent proposals                         ║
    ║        │                                                       ║
    ║        ▼                                                       ║
    ║ [2] Find Suppliers (R4-R5) + AI Recommendations             ║
    ║     ├─ Query & compare up to 3 suppliers                     ║
    ║     ├─ AI evaluates: price, reliability, quality             ║
    ║     ├─ Reviews past supplier performance (memory)            ║
    ║     └─ Recommends best option with reasoning                 ║
    ║        │                                                       ║
    ║        ▼                                                       ║
    ║ [3] Create Purchase Order (R6-R8) + AI Approval Advice      ║
    ║     ├─ Generate order with intelligent justification         ║
    ║     ├─ AI provides approval recommendation                   ║
    ║     ├─ Adjusts qty for min order & packaging units          ║
    ║     └─ Status: pending_approval                              ║
    ║        │                                                       ║
    ║        ▼                                                       ║
    ║ [4] Human Approval (R6-R8)                                  ║
    ║     ├─ Manager reviews AI recommendation                     ║
    ║     ├─ Approve/reject with full context                      ║
    ║     └─ Decision stored in memory                             ║
    ║        │                                                       ║
    ║        ▼                                                       ║
    ║ [5] Invoice Verification (R9-R10)                           ║
    ║     ├─ Automated invoice vs PO comparison                    ║
    ║     ├─ Detect price & quantity discrepancies                 ║
    ║     └─ Alert on anomalies                                    ║
    ║        │                                                       ║
    ║        ▼                                                       ║
    ║ [6] Supplier History Tracking (R11)                         ║
    ║     ├─ Update performance metrics                            ║
    ║     ├─ Track: price history, late deliveries, quality       ║
    ║     └─ Feed into future AI decisions                         ║
    ║                                                                ║
    ║ 🧠 MEMORY: All AI reasoning stored for continuous learning   ║
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


