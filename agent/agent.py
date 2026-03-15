from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from agent.utils.state import ProcurementState
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


llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview",
    temperature=0.7,
)

# Globale database connectie voor checkpointing
DB_PATH = os.path.join(os.path.dirname(__file__), '../db/checkpoints.sqlite')
_checkpointer = None

def get_checkpointer():
    """Get of maak een persistent checkpointer"""
    global _checkpointer
    if _checkpointer is None:
        # Maak database connectie die open blijft
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
    return _checkpointer

def _state_get(state: ProcurementState, key: str, default=None):
    """Read state values from either dict-like or object-like ProcurementState."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)

def route_after_inventory(state: ProcurementState) -> str:
    """op basis van status van de inventarisatie, route bepalen"""
    if _state_get(state, "status") == "proposed":
        return "find_suppliers"
    # After regular inventory, check for new releases
    return "check_existing_new_releases"

def route_after_new_release_check(state: ProcurementState) -> str:
    """Route after checking existing new releases"""
    next_action = _state_get(state, "next_action", "scan_for_new_releases")

    if next_action == "create_restock_orders":
        return "find_suppliers"  # Use existing supplier/order flow
    if next_action == "scan_for_new_releases":
        return "detect_new_releases"
    return "end"

def route_after_new_release_detection(state: ProcurementState) -> str:
    """Route after detecting new releases"""
    next_action = _state_get(state, "next_action", "complete")

    if next_action == "create_new_release_orders":
        return "create_new_release_orders"
    return "end"

def route_after_approval(state: ProcurementState) -> str:
    """Route based on approval status"""
    approved_orders = _state_get(state, "approved_orders")
    rejection_reasons = _state_get(state, "rejection_reasons")
    approval_decision = _state_get(state, "approval_decision")

    # If any decision has been made, process it
    if approved_orders or rejection_reasons or approval_decision:
        return "process_approval"
    # If still awaiting human input, pause workflow
    if _state_get(state, "step") == "awaiting_human_input":
        return "end"
    return "end"

def create_procurement_workflow():
    workflow = StateGraph(ProcurementState)

    # Herstel alle bestaande nodes
    workflow.add_node("process_due_deliveries", process_due_deliveries_node)
    workflow.add_node("daily_inventory_check", daily_inventory_check_node)
    workflow.add_node("find_suppliers", find_suppliers_node)
    workflow.add_node("create_purchase_order", create_purchase_order_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("process_approval", process_approval_node_workflow)

    workflow.add_node("check_existing_new_releases", check_existing_new_releases_node)
    workflow.add_node("detect_new_releases", detect_new_releases_node)
    workflow.add_node("create_new_release_orders", create_new_release_orders_node)

    workflow.set_entry_point("process_due_deliveries")
    workflow.add_edge("process_due_deliveries", "daily_inventory_check")

    workflow.add_conditional_edges(
        "daily_inventory_check",
        route_after_inventory,
        {
            "find_suppliers": "find_suppliers",
            "check_existing_new_releases": "check_existing_new_releases"
        }
    )

    # Vereenvoudigde new release flow
    workflow.add_edge("check_existing_new_releases", "detect_new_releases")
    workflow.add_edge("detect_new_releases", "create_new_release_orders")
    workflow.add_edge("create_new_release_orders", END)

    # Herstel overige routes
    workflow.add_edge("find_suppliers", "create_purchase_order")
    workflow.add_edge("create_purchase_order", "human_approval")
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
