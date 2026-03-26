import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.agent import create_procurement_workflow
from agent.procurement_data import ProcurementDatabase
from agent.utils.state import ProcurementState


def _db_dir() -> Path:
    return Path(__file__).parent.parent.parent / "db"


def run_until_node(workflow_graph, initial_state: ProcurementState, config: dict, target_node: str, max_steps: int = 20):
    visited = []
    latest = None

    for index, step_output in enumerate(workflow_graph.stream(initial_state.model_dump(), config), start=1):
        node_name = list(step_output.keys())[0]
        node_state = step_output[node_name]
        visited.append(node_name)
        latest = ProcurementState(**node_state)

        if node_name == target_node:
            break
        if index >= max_steps:
            break

    return latest, visited


def resume_with_approval(
    workflow_graph,
    paused_state: ProcurementState,
    config: dict,
    approved_indices=None,
    rejected_by_index=None,
    approved_by="test_manager",
):
    approved_indices = approved_indices or []
    rejected_by_index = rejected_by_index or {}

    resume_state = ProcurementState(**paused_state.model_dump())
    resume_state.approval_order_indices = approved_indices
    resume_state.rejection_reasons_by_index = rejected_by_index
    resume_state.approval_decision = "approved" if approved_indices else "rejected"
    resume_state.approved_by = approved_by

    latest = None
    visited = []
    for step_output in workflow_graph.stream(resume_state.model_dump(), config):
        node_name = list(step_output.keys())[0]
        node_state = step_output[node_name]
        visited.append(node_name)
        latest = ProcurementState(**node_state)

    return latest, visited


@pytest.fixture(autouse=True)
def restore_database_files():
    db_dir = _db_dir()
    tracked_files = [
        "inventory.json",
        "product.json",
        "purchase_order.json",
        "purchase_order_item.json",
        "price_history.json",
        "sales.json",
        "supplier_performance.json",
        "decision_log.db",
    ]

    snapshots = {}
    for filename in tracked_files:
        file_path = db_dir / filename
        snapshots[filename] = file_path.read_bytes() if file_path.exists() else None

    yield

    for filename, content in snapshots.items():
        file_path = db_dir / filename
        if content is None:
            if file_path.exists():
                file_path.unlink()
            continue
        file_path.write_bytes(content)


@pytest.fixture(autouse=True)
def mock_external_dependencies():
    with (
        patch("agent.utils.nodes.supplier_nodes.ChatGoogleGenerativeAI") as supplier_llm_cls,
        patch("agent.utils.nodes.order_nodes.ChatGoogleGenerativeAI") as order_llm_cls,
        patch("agent.utils.nodes.new_release_nodes.SpotifyClient") as spotify_cls,
        patch("random.sample", side_effect=lambda population, k: list(population)[:k]),
        patch("random.uniform", return_value=1.0),
        patch("random.randint", return_value=7),
    ):
        supplier_llm = Mock()
        supplier_llm.invoke.return_value = Mock(content="{}")
        supplier_llm_cls.return_value = supplier_llm

        order_llm_cls.return_value = Mock()

        spotify_client = Mock()
        spotify_client.get_market_popular_albums.return_value = []
        spotify_client.get_new_releases.return_value = []
        spotify_cls.return_value = spotify_client

        yield {
            "spotify_client": spotify_client,
        }


@pytest.fixture
def db():
    return ProcurementDatabase()


@pytest.fixture
def workflow_graph():
    return create_procurement_workflow()
