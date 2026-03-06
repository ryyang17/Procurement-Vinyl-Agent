from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from agent.utils.state import ProcurementState
from agent.utils.nodes.inventory_nodes import daily_inventory_check_node
from agent.utils.nodes.supplier_nodes import find_suppliers_node
from agent.utils.nodes.order_nodes import create_purchase_order_node
from agent.utils.nodes.approval_nodes import human_approval_node, process_approval_node_workflow
from agent.utils.nodes.delivery_nodes import process_due_deliveries_node
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

def route_after_inventory(state: ProcurementState) -> str:
    """op basis van status van de inventarisatie, route bepalen"""
    if state.status == 'proposed':
        return "find_suppliers"
    else:
        return "end"

def route_after_approval(state: ProcurementState) -> str:
    """Route based on approval status"""
    # Check if human has made any approval decision
    has_approved_orders = hasattr(state, 'approved_orders') and state.approved_orders
    has_rejection_reasons = hasattr(state, 'rejection_reasons') and state.rejection_reasons
    has_approval_decision = hasattr(state, 'approval_decision') and state.approval_decision

    # If any decision has been made, process it
    if has_approved_orders or has_rejection_reasons or has_approval_decision:
        return "process_approval"
    # If still awaiting human input, pause workflow
    elif state.step == "awaiting_human_input":
        return "end"
    else:
        return "end"

def create_procurement_workflow():
    workflow = StateGraph(ProcurementState)

    workflow.add_node("process_due_deliveries", process_due_deliveries_node)
    workflow.add_node("daily_inventory_check", daily_inventory_check_node)
    workflow.add_node("find_suppliers", find_suppliers_node)
    workflow.add_node("create_purchase_order", create_purchase_order_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("process_approval", process_approval_node_workflow)

    workflow.set_entry_point("process_due_deliveries")

    # First process deliveries, then check inventory
    workflow.add_edge("process_due_deliveries", "daily_inventory_check")

    workflow.add_conditional_edges(
        "daily_inventory_check",
        route_after_inventory,
        {
            "find_suppliers": "find_suppliers",
            "end": END
        }
    )

    workflow.add_edge("find_suppliers", "create_purchase_order")
    workflow.add_edge("create_purchase_order", "human_approval")

    # After approval, route based on decision
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "process_approval": "process_approval",
            "end": END
        }
    )

    # After processing approval, end
    workflow.add_edge("process_approval", END)

    # SqliteSaver voor persistent checkpointing
    # Beslissingen en state worden bewaard in checkpoints.sqlite
    # Bij herstart kan de workflow hervat worden met dezelfde thread_id
    checkpointer = get_checkpointer()

    return workflow.compile(checkpointer=checkpointer)

