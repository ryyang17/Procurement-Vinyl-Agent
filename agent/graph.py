from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from agent.models import ProcurementState
from agent.nodes.inventory_nodes import daily_inventory_check_node
from pathlib import Path

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-3-pro-preview",
    temperature=1,
    max_tokens=1000
)

# Keep workflow checkpoint storage separate from business procurement DB.
CHECKPOINT_DB_PATH = Path("workflow_memory.db")

# Initialize SqliteSaver for checkpointing
memory = SqliteSaver(str(CHECKPOINT_DB_PATH))


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
    workflow = StateGraph(ProcurementState)

    workflow.add_node("daily_inventory_check", daily_inventory_check_node)
    workflow.set_entry_point("daily_inventory_check")
    workflow.set_finish_point("daily_inventory_check")

    # Altijd de checkpointer meegeven
    return workflow.compile(checkpointer=memory)
