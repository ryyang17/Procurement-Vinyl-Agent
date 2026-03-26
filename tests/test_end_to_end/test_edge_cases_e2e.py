import uuid
from datetime import date, datetime, timedelta

from agent.utils.state import ProcurementState
from tests.test_end_to_end.e2e_test_utils import run_until_node, resume_with_approval


class TestEdgeCasesE2E:
    def test_ec1_vertraagde_levering_beinvloedt_toekomstige_leverancierskeuze(self, workflow_graph, db):
        inventory = db.get_inventory()
        products = db.get_products()
        target_product = products[0]

        # Keep this scenario focused on one product so supplier choice is comparable.
        for item in inventory:
            item["quantity_in_stock"] = 999
            if item["product_id"] == target_product["product_id"]:
                item["quantity_in_stock"] = 0
        db.save_json("inventory.json", inventory)

        thread_id = f"ec1-phase1-{uuid.uuid4()}"
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

        reject_index = 0
        rejected_supplier_id = draft_orders[reject_index]["supplier_id"]

        perf_before = db.get_supplier_performance()
        rejected_supplier_before = next(p for p in perf_before if p["supplier_id"] == rejected_supplier_id)
        late_before = rejected_supplier_before["late_deliveries"]

        resume_with_approval(
            workflow_graph,
            state_at_create_order,
            config,
            approved_indices=[],
            rejected_by_index={reject_index: "Vertraging in levering - bestelling was 5 dagen te laat"},
            approved_by="inkoop_manager",
        )

        perf_after = db.get_supplier_performance()
        rejected_supplier_after = next(p for p in perf_after if p["supplier_id"] == rejected_supplier_id)
        assert rejected_supplier_after["late_deliveries"] == late_before + 1

        second_thread_id = f"ec1-phase2-{uuid.uuid4()}"
        second_state = ProcurementState(thread_id=second_thread_id)
        second_config = {"configurable": {"thread_id": second_thread_id}}
        supplier_state, _ = run_until_node(workflow_graph, second_state, second_config, target_node="find_suppliers")

        selections = supplier_state.data.get("supplier_selections", [])
        target_selection = next((s for s in selections if s.get("product_id") == target_product["product_id"]), None)
        assert target_selection is not None

        option_ids = [opt["supplier_id"] for opt in target_selection.get("all_options", [])]
        if rejected_supplier_id in option_ids:
            rejected_option = next(
                opt for opt in target_selection.get("all_options", [])
                if opt["supplier_id"] == rejected_supplier_id
            )
            assert rejected_option["late_deliveries_count"] == late_before + 1

    def test_ec2_leverancier_niet_op_voorraad_alternatief_of_logging(self, workflow_graph, db):
        perf = db.get_supplier_performance()
        for row in perf:
            row["temporarily_unavailable"] = True
            row["unavailable_since"] = datetime.now().isoformat()
        db.save_json("supplier_performance.json", perf)

        inventory = db.get_inventory()
        products = db.get_products()
        target_product = products[0]
        inventory_item = next(i for i in inventory if i["product_id"] == target_product["product_id"])
        inventory_item["quantity_in_stock"] = 0
        db.save_json("inventory.json", inventory)

        thread_id = f"ec2-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        supplier_state, _ = run_until_node(workflow_graph, initial_state, config, target_node="find_suppliers")

        assert supplier_state is not None
        assert supplier_state.status == "no_suppliers_found"
        assert len(supplier_state.data.get("supplier_selections", [])) == 0

    def test_ec3_prijsfluctuatie_detectie_met_waarschuwing(self, workflow_graph, db):
        price_history = db.get_price_history()
        products = db.get_products()
        target_product = products[0]
        product_id = target_product["product_id"]

        today = date.today()
        price_history.append({
            "product_id": product_id,
            "date": (today - timedelta(days=10)).isoformat(),
            "price": 20.0,
        })
        price_history.append({
            "product_id": product_id,
            "date": today.isoformat(),
            "price": 33.0,
        })
        db.save_json("price_history.json", price_history)

        thread_id = f"ec3-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        analysed_state, visited = run_until_node(
            workflow_graph,
            initial_state,
            config,
            target_node="analyse_sales_velocity",
        )

        assert "analyse_sales_velocity" in visited
        assert analysed_state is not None
        alerts = analysed_state.data.get("price_fluctuation_alerts", [])
        assert len(alerts) > 0
        assert any(a["product_id"] == product_id for a in alerts)

    def test_ec4_nieuwe_release_detectie_en_bestelvoorstel(self, workflow_graph, db, mock_external_dependencies):
        spotify = mock_external_dependencies["spotify_client"]
        spotify.get_market_popular_albums.return_value = []
        spotify.get_new_releases.return_value = [
            {
                "id": "spotify-release-ec4",
                "title": "Future Echoes",
                "artist": "Nova Lines",
                "genre": "Synthwave",
                "release_date": date.today().isoformat(),
                "market_popularity_score": 76,
            }
        ]

        thread_id = f"ec4-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state, visited = run_until_node(workflow_graph, initial_state, config, target_node="create_new_release_orders")

        assert "create_new_release_orders" in visited
        assert state is not None
        proposals = state.purchase_order_proposals
        assert len(proposals) > 0
        assert proposals[0]["product_id"] == "spotify-release-ec4"

    def test_ec5_populariteit_beinvloedt_bestelhoeveelheid(self, workflow_graph, mock_external_dependencies):
        spotify = mock_external_dependencies["spotify_client"]
        spotify.get_market_popular_albums.return_value = []
        spotify.get_new_releases.return_value = [
            {
                "id": "spotify-release-high",
                "title": "Mass Appeal",
                "artist": "Peak Charts",
                "genre": "Pop",
                "release_date": date.today().isoformat(),
                "market_popularity_score": 91,
            },
            {
                "id": "spotify-release-medium",
                "title": "Steady Spin",
                "artist": "Side B",
                "genre": "Rock",
                "release_date": date.today().isoformat(),
                "market_popularity_score": 73,
            },
            {
                "id": "spotify-release-low",
                "title": "Niche Cut",
                "artist": "Underground",
                "genre": "Alternative",
                "release_date": date.today().isoformat(),
                "market_popularity_score": 55,
            },
        ]

        thread_id = f"ec5-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state, _ = run_until_node(workflow_graph, initial_state, config, target_node="create_new_release_orders")

        qty_by_product = {proposal["product_id"]: proposal["quantity"] for proposal in state.purchase_order_proposals}
        assert qty_by_product["spotify-release-high"] == 10
        assert qty_by_product["spotify-release-medium"] == 8
        assert qty_by_product["spotify-release-low"] == 5

    def test_ec6_verkoopsnelheid_voorspelt_stockout_en_reorder(self, workflow_graph, db):
        inventory = db.get_inventory()
        products = db.get_products()
        target_product = products[0]
        inventory_item = next(i for i in inventory if i["product_id"] == target_product["product_id"])

        # Force low stock so sales velocity forecast should trigger a reorder recommendation.
        inventory_item["quantity_in_stock"] = 5
        inventory_item["reorder_level"] = 1
        db.save_json("inventory.json", inventory)

        thread_id = f"ec6-{uuid.uuid4()}"
        initial_state = ProcurementState(thread_id=thread_id)
        config = {"configurable": {"thread_id": thread_id}}

        state_at_inventory, visited = run_until_node(
            workflow_graph,
            initial_state,
            config,
            target_node="daily_inventory_check",
        )

        assert "analyse_sales_velocity" in visited
        forecasts = state_at_inventory.data.get("sales_velocity_forecasts", [])
        product_forecast = next((f for f in forecasts if f["product_id"] == target_product["product_id"]), None)
        assert product_forecast is not None
        assert product_forecast["days_until_stockout"] is not None
        assert product_forecast["reorder_recommended"] is True

        dynamic_levels = state_at_inventory.data.get("dynamic_reorder_levels", {})
        assert str(target_product["product_id"]) in dynamic_levels
        assert dynamic_levels[str(target_product["product_id"])] > inventory_item["reorder_level"]

        reorder_proposals = state_at_inventory.data.get("reorder_proposals", [])
        assert len(reorder_proposals) > 0
        target_proposal = next((p for p in reorder_proposals if p.get("product_id") == target_product["product_id"]), None)
        if target_proposal is not None:
            assert target_proposal.get("reorder_basis") == "sales_velocity"
