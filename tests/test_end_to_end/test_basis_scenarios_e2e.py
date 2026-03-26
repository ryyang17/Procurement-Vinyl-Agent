import uuid
from datetime import datetime, timedelta

from agent.utils.state import ProcurementState
from tests.test_end_to_end.e2e_test_utils import run_until_node, resume_with_approval


class TestBasisScenarioE2E:
    def test_t1_voorraadtekort_detectie_end_to_end(self, workflow_graph, db):
        inventory = db.get_inventory()
        products = db.get_products()

        target_product = products[0]
        inventory_item = next(i for i in inventory if i["product_id"] == target_product["product_id"])
        inventory_item["quantity_in_stock"] = 0
        db.save_json("inventory.json", inventory)

        thread_id = f"t1-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state, visited = run_until_node(workflow_graph, initial_state, config, target_node="daily_inventory_check")

        assert "daily_inventory_check" in visited
        assert state is not None
        assert state.status == "proposed"
        assert len(state.data.get("reorder_proposals", [])) > 0

    def test_t2_leveranciers_vergelijken_end_to_end(self, workflow_graph, db):
        inventory = db.get_inventory()
        products = db.get_products()

        target_product = products[0]
        inventory_item = next(i for i in inventory if i["product_id"] == target_product["product_id"])
        inventory_item["quantity_in_stock"] = 0
        db.save_json("inventory.json", inventory)

        thread_id = f"t2-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state, visited = run_until_node(workflow_graph, initial_state, config, target_node="find_suppliers")

        assert "find_suppliers" in visited
        assert state is not None
        assert state.status in ["suppliers_selected", "no_suppliers_found"]

        selections = state.data.get("supplier_selections", [])
        assert len(selections) > 0
        for selection in selections:
            options = selection.get("all_options", [])
            assert 1 <= len(options) <= 3
            assert selection.get("selected_supplier") is not None

    def test_t3_conceptbestelling_opstellen_end_to_end(self, workflow_graph, db):
        inventory = db.get_inventory()
        products = db.get_products()

        target_product = products[0]
        inventory_item = next(i for i in inventory if i["product_id"] == target_product["product_id"])
        inventory_item["quantity_in_stock"] = 0
        db.save_json("inventory.json", inventory)

        thread_id = f"t3-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state, visited = run_until_node(workflow_graph, initial_state, config, target_node="create_purchase_order")

        assert "create_purchase_order" in visited
        assert state is not None
        assert state.status == "awaiting_approval"

        draft_orders = state.data.get("draft_orders", [])
        assert len(draft_orders) > 0
        for order in draft_orders:
            assert "supplier_id" in order
            assert "supplier_name" in order
            assert len(order.get("items", [])) > 0
            assert order.get("total_amount", 0) >= 0

    def test_t4_human_approval_end_to_end(self, workflow_graph, db):
        inventory = db.get_inventory()
        products = db.get_products()

        target_product = products[0]
        inventory_item = next(i for i in inventory if i["product_id"] == target_product["product_id"])
        inventory_item["quantity_in_stock"] = 0
        db.save_json("inventory.json", inventory)

        thread_id = f"t4-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state_at_create_order, _ = run_until_node(
            workflow_graph,
            initial_state,
            config,
            target_node="create_purchase_order",
        )
        assert state_at_create_order is not None

        draft_orders = state_at_create_order.data.get("draft_orders", [])
        assert len(draft_orders) > 0

        final_state, visited_after_resume = resume_with_approval(
            workflow_graph,
            state_at_create_order,
            config,
            approved_indices=[0],
            rejected_by_index={},
            approved_by="inkoop_manager",
        )

        assert "process_approval" in visited_after_resume
        assert final_state is not None
        assert final_state.status == "orders_placed"
        assert len(final_state.data.get("created_orders", [])) == 1

    def test_t5_order_plaatsen_en_voorraad_bijwerken_end_to_end(self, workflow_graph, db):
        inventory = db.get_inventory()
        products = db.get_products()

        target_product = products[0]
        inventory_item = next(i for i in inventory if i["product_id"] == target_product["product_id"])
        inventory_item["quantity_in_stock"] = 0
        db.save_json("inventory.json", inventory)

        inventory_before = {i["product_id"]: i["quantity_in_stock"] for i in inventory}

        thread_id = f"t5-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state_at_create_order, _ = run_until_node(
            workflow_graph,
            initial_state,
            config,
            target_node="create_purchase_order",
        )
        final_state, _ = resume_with_approval(
            workflow_graph,
            state_at_create_order,
            config,
            approved_indices=list(range(len(state_at_create_order.data.get("draft_orders", [])))),
            approved_by="inkoop_manager",
        )

        created_orders = final_state.data.get("created_orders", [])
        assert len(created_orders) > 0

        orders = db.get_purchase_orders()
        for created in created_orders:
            for order in orders:
                if order["purchase_order_id"] == created["order_id"]:
                    order["expected_delivery_date"] = (datetime.now() - timedelta(days=1)).isoformat()
        db.save_json("purchase_order.json", orders)

        delivery_thread_id = f"t5-delivery-{uuid.uuid4()}"
        delivery_state = ProcurementState(thread_id=delivery_thread_id)
        delivery_config = {"configurable": {"thread_id": delivery_thread_id}}
        state_after_delivery, visited = run_until_node(
            workflow_graph,
            delivery_state,
            delivery_config,
            target_node="process_due_deliveries",
        )

        assert "process_due_deliveries" in visited
        assert state_after_delivery is not None
        assert len(state_after_delivery.data.get("processed_deliveries", [])) > 0

        updated_inventory = db.get_inventory()
        inventory_after = {i["product_id"]: i["quantity_in_stock"] for i in updated_inventory}

        order_items = db.get_purchase_order_items()
        created_order_ids = {o["order_id"] for o in created_orders}
        delivered_product_ids = {
            item["product_id"]
            for item in order_items
            if item["purchase_order_id"] in created_order_ids
        }
        assert len(delivered_product_ids) > 0
        assert any(
            inventory_after.get(pid, 0) > inventory_before.get(pid, 0)
            for pid in delivered_product_ids
        )
