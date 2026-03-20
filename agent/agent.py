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


def _normalize_path_choice(path_choice: str | None) -> str | None:
    """Accept both UI and backend aliases for path selection values."""
    if path_choice is None:
        return None

    aliases = {
        "path_1_suppliers": "path_1_suppliers",
        "find_suppliers": "path_1_suppliers",
        "suppliers": "path_1_suppliers",
        "path_2_new_releases": "path_2_new_releases",
        "check_existing_new_releases": "path_2_new_releases",
        "new_releases": "path_2_new_releases",
    }
    return aliases.get(str(path_choice).strip(), None)

# Bepaal routing na goedkeuring
def route_after_approval(state: ProcurementState) -> str:
    # Support both legacy and current frontend fields.
    approved_orders = _state_get(state, "approved_orders") or _state_get(state, "approval_order_indices")
    rejection_reasons = _state_get(state, "rejection_reasons") or _state_get(state, "rejection_reasons_by_index")
    approval_decision = _state_get(state, "approval_decision")
    awaiting_human_approval = _state_get(state, "awaiting_human_approval")

    # Als er een beslissing is, ga naar process_approval
    if approved_orders or rejection_reasons or approval_decision:
        return "process_approval"
    # Als er nog gewacht wordt op input, stop workflow
    if awaiting_human_approval or _state_get(state, "step") == "awaiting_human_input":
        return "end"
    return "end"


def route_after_inventory(state: ProcurementState) -> str:
    path_choice = _normalize_path_choice(_state_get(state, "path_choice"))
    awaiting_path_selection = _state_get(state, "awaiting_path_selection")

    # Keep state canonical to avoid drift between frontend and backend values.
    if path_choice is not None:
        if isinstance(state, dict):
            state["path_choice"] = path_choice
        else:
            state.path_choice = path_choice

    # Geen keuze gemaakt: ga naar path selection node (zal daar pauzeren).
    if path_choice is None:
        return "await_path_selection"

    # Keuze gemaakt: route naar juiste pad
    if path_choice == "path_1_suppliers":
        return "find_suppliers"
    elif path_choice == "path_2_new_releases":
        return "check_existing_new_releases"

    # Onbekende keuze: ga terug naar path selection node.
    return "await_path_selection"


def route_from_path_selection(state: ProcurementState) -> str:
    """
    Route vanaf de await_path_selection node.
    Als we al wachten op human input en er is nog geen keuze,
    dan stoppen we de graph-run zodat HITL netjes pauzeert.
    """
    path_choice = _normalize_path_choice(_state_get(state, "path_choice"))
    step = _state_get(state, "step")

    if step == "awaiting_human_input" and path_choice is None:
        return "end"

    if path_choice == "path_1_suppliers":
        return "find_suppliers"
    elif path_choice == "path_2_new_releases":
        return "check_existing_new_releases"

    return "await_path_selection"


def route_after_new_release_check(state: ProcurementState) -> str:
    """Route after checking existing new releases."""
    next_action = _state_get(state, "next_action")

    if next_action == "detect_new_releases" or next_action == "scan_for_new_releases":
        return "detect_new_releases"
    elif next_action == "create_restock_orders":
        # For now, route to create_new_release_orders as it handles both cases
        return "create_new_release_orders"
    else:
        return "detect_new_releases"


def route_after_new_release_detection(state: ProcurementState) -> str:
    """Route after detecting new releases from Spotify."""
    next_action = _state_get(state, "next_action")
    new_releases = _state_get(state, "new_releases", [])

    if next_action == "create_new_release_orders" and new_releases:
        return "create_new_release_orders"
    elif next_action == "end" or not new_releases:
        return "human_approval"  # Show empty approval panel
    else:
        return "create_new_release_orders"

# Node die wacht op user path selection
def await_path_selection_node(state: ProcurementState) -> ProcurementState:
    """
    Workflow pauses here, waiting for user to select a path via frontend UI.
    The frontend will update the state with path_choice and resume.
    """
    path_choice = _normalize_path_choice(_state_get(state, "path_choice"))

    # Als user al gekozen heeft, niet opnieuw pauzeren maar direct doorstromen.
    if path_choice is not None:
        if isinstance(state, dict):
            state["path_choice"] = path_choice
            state["awaiting_path_selection"] = False
            state["status"] = "path_selected"
            state["step"] = "path_selected"  # Clear awaiting_human_input
            state["message"] = "Pad geselecteerd. Workflow wordt hervat."
            return ProcurementState(**state)
        state.path_choice = path_choice
        state.awaiting_path_selection = False
        state.status = "path_selected"
        state.step = "path_selected"  # Clear awaiting_human_input
        state.message = "Pad geselecteerd. Workflow wordt hervat."
        return state

    if isinstance(state, dict):
        state["awaiting_path_selection"] = True
        # Zelfde HITL contract als human approval: workflow pauzeert op awaiting_human_input.
        state["step"] = "awaiting_human_input"
        state["status"] = "awaiting_path_selection"
        state["message"] = "Selecteer een werkstroom: Pad 1 (Leveranciers zoeken) of Pad 2 (Controleer nieuwe releases)"
        return ProcurementState(**state)
    state.awaiting_path_selection = True
    # Zelfde HITL contract als human approval: workflow pauzeert op awaiting_human_input.
    state.step = "awaiting_human_input"
    state.status = "awaiting_path_selection"
    state.message = "Selecteer een werkstroom: Pad 1 (Leveranciers zoeken) of Pad 2 (Controleer nieuwe releases)"
    return state


def create_procurement_workflow():
    workflow = StateGraph(ProcurementState)

    workflow.add_node("process_due_deliveries", process_due_deliveries_node)
    workflow.add_node("daily_inventory_check", daily_inventory_check_node)

    # Node dat wacht op path selection van user
    workflow.add_node("await_path_selection", await_path_selection_node)

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

    # Kies pad: leveranciers of nieuwe releases op basis van user input
    workflow.add_conditional_edges(
        "daily_inventory_check",
        route_after_inventory,
        {
            "await_path_selection": "await_path_selection",
            "find_suppliers": "find_suppliers",
            "check_existing_new_releases": "check_existing_new_releases",
        }
    )

    # Wanneer path selection gemaakt is, route naar juiste pad
    workflow.add_conditional_edges(
        "await_path_selection",
        route_from_path_selection,
        {
            "end": END,
            "find_suppliers": "find_suppliers",
            "check_existing_new_releases": "check_existing_new_releases",
        }
    )

    # New release path routing
    workflow.add_conditional_edges(
        "check_existing_new_releases",
        route_after_new_release_check,
        {
            "detect_new_releases": "detect_new_releases",
            "create_new_release_orders": "create_new_release_orders",
        }
    )

    workflow.add_conditional_edges(
        "detect_new_releases",
        route_after_new_release_detection,
        {
            "create_new_release_orders": "create_new_release_orders",
            "human_approval": "human_approval",
        }
    )

    workflow.add_edge("create_new_release_orders", "human_approval")

    # Supplier path routing
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
