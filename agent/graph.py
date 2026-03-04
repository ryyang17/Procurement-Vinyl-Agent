from dotenv import load_dotenv
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from agent.models import ProcurementState
from agent.nodes.inventory_nodes import daily_inventory_check_node
from agent.nodes.supplier_nodes import find_suppliers_node
from agent.nodes.order_nodes import create_purchase_order_node
from agent.nodes.approval_nodes import human_approval_node
from langgraph.graph import StateGraph, END

llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview",
    temperature=0.7,
)

def route_after_inventory(state: ProcurementState) -> str:
    """Route based on inventory check results"""
    if state.status == 'proposed':
        return "find_suppliers"
    else:
        return "end"

def route_after_approval(state: ProcurementState) -> str:
    """Route based on approval status"""
    if state.step == "awaiting_human_input":
        return "end"  # Exit workflow
    else:
        return "end"

def create_procurement_workflow():

    workflow = StateGraph(ProcurementState)

    # Add all nodes
    workflow.add_node("daily_inventory_check", daily_inventory_check_node)
    workflow.add_node("find_suppliers", find_suppliers_node)
    workflow.add_node("create_purchase_order", create_purchase_order_node)
    workflow.add_node("human_approval", human_approval_node)

    # Set entry point
    workflow.set_entry_point("daily_inventory_check")

    # Add conditional edges
    workflow.add_conditional_edges(
        "daily_inventory_check",
        route_after_inventory,
        {
            "find_suppliers": "find_suppliers",
            "end": END
        }
    )

    # flow after suppliers
    workflow.add_edge("find_suppliers", "create_purchase_order")
    workflow.add_edge("create_purchase_order", "human_approval")

    # After approval, route to end
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "end": END
        }
    )

    return workflow.compile()
