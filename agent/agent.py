from dotenv import load_dotenv
load_dotenv()


from langchain_google_genai import ChatGoogleGenerativeAI
from agent.utils.state import ProcurementState
# Importeer nodes voor goedkeuring, levering, voorraad, orders, leveranciers en nieuwe releases
from agent.utils.nodes.approval_nodes import human_approval_node, process_approval_node_workflow
from agent.utils.nodes.delivery_nodes import process_due_deliveries_node
from agent.utils.nodes.inventory_nodes import daily_inventory_check_node
from agent.utils.nodes.order_nodes import create_purchase_order_node
from agent.utils.nodes.supplier_nodes import find_suppliers_node
from agent.utils.nodes.new_release_nodes import (
    detect_new_releases_node,
    create_new_release_orders_node,
    check_existing_new_releases_node
)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
import os
import sqlite3

# Initialiseer LLM voor workflow
llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview",
    temperature=0.7,
    api_key=os.getenv("GOOGLE_API_KEY")
)

# Pad naar database voor checkpointing
DB_PATH = os.path.join(os.path.dirname(__file__), '../db/checkpoints.sqlite')
_checkpointer = None

# Haal of maak een checkpointer voor workflow persistentie
def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        # Maak database connectie die open blijft
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
    return _checkpointer

# Haal waarde uit state object of dict
def _state_get(state: ProcurementState, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)

# Bepaal routing na goedkeuring
def route_after_approval(state: ProcurementState) -> str:
    approved_orders = _state_get(state, "approved_orders")
    rejection_reasons = _state_get(state, "rejection_reasons")
    approval_decision = _state_get(state, "approval_decision")

    # Als er een beslissing is, ga naar process_approval
    if approved_orders or rejection_reasons or approval_decision:
        return "process_approval"
    # Als er nog gewacht wordt op input, stop workflow
    if _state_get(state, "step") == "awaiting_human_input":
        return "end"
    return "end"

# Bepaal routing na voorraadcontrole
def route_after_inventory(state: ProcurementState) -> str:
    next_action = _state_get(state, "next_action")
    if next_action == "find_suppliers":
        return "find_suppliers"
    elif next_action == "check_existing_new_releases":
        return "check_existing_new_releases"

    return "find_suppliers"


def create_procurement_workflow():
    workflow = StateGraph(ProcurementState)

    workflow.add_node("process_due_deliveries", process_due_deliveries_node)
    workflow.add_node("daily_inventory_check", daily_inventory_check_node)

    # Pad 1: Leveranciers -> Inkooporder -> Goedkeuring
    workflow.add_node("find_suppliers", find_suppliers_node)
    workflow.add_node("create_purchase_order", create_purchase_order_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("process_approval", process_approval_node_workflow)

    # Pad 2: Nieuwe releases -> Detectie -> Order -> Goedkeuring
    workflow.add_node("check_existing_new_releases", check_existing_new_releases_node)
    workflow.add_node("detect_new_releases", detect_new_releases_node)
    workflow.add_node("create_new_release_orders", create_new_release_orders_node)

    # Startpunt van de workflow
    workflow.set_entry_point("process_due_deliveries")
    workflow.add_edge("process_due_deliveries", "daily_inventory_check")

    # Kies pad: leveranciers of nieuwe releases
    workflow.add_conditional_edges(
        "daily_inventory_check",
        route_after_inventory,
        {
            "find_suppliers": "find_suppliers",
            "check_existing_new_releases": "check_existing_new_releases"
        }
    )

    workflow.add_edge("check_existing_new_releases", "detect_new_releases")
    workflow.add_edge("detect_new_releases", "create_new_release_orders")
    workflow.add_edge("create_new_release_orders", "human_approval")

    workflow.add_edge("find_suppliers", "create_purchase_order")
    workflow.add_edge("create_purchase_order", "human_approval")

    # Na goedkeuring: verwerk of stop
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "process_approval": "process_approval",
            "end": END
        }
    )
    workflow.add_edge("process_approval", END)

    checkpointer = get_checkpointer()
    return workflow.compile(checkpointer=checkpointer)
