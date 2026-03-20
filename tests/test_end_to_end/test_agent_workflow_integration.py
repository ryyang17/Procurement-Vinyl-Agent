"""
Integration test voor de volledige agent workflow
Test de echte agent StateGraph end-to-end
"""
import pytest
import sys
import uuid
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import create_procurement_workflow
from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase


class TestAgentWorkflowIntegration:
    """End-to-end integration tests voor de volledige agent workflow"""

    @pytest.fixture
    def workflow_graph(self):
        """Create the compiled workflow graph"""
        return create_procurement_workflow()

    @pytest.fixture
    def db(self):
        """Database fixture"""
        return ProcurementDatabase()

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM to avoid API calls"""
        with patch('agent.utils.nodes.supplier_nodes.llm') as mock:
            response = Mock()
            response.content = "LEVERANCIER: Vinyl Distributors BV\nREDEN: Best price and reliability"
            mock.invoke.return_value = response
            yield mock

    def test_complete_workflow_shortage_to_approval(self, workflow_graph, db, mock_llm):
        """
        Test de complete workflow: van voorraadtekort tot human approval
        Dit test de échte agent met StateGraph routing
        """
        print("\n" + "="*80)
        print("INTEGRATION TEST: COMPLETE WORKFLOW - SHORTAGE TO APPROVAL")
        print("="*80)

        # Step 1: Setup - Ensure we have low stock
        inventory = db.get_inventory()
        products = db.get_products()

        # Force a product to be low on stock for testing
        test_product = products[0]
        test_inventory = next(
            (i for i in inventory if i['product_id'] == test_product['product_id']),
            None
        )

        if test_inventory:
            original_stock = test_inventory['quantity_in_stock']
            test_inventory['quantity_in_stock'] = 0  # Force low stock
            db.save_json('inventory.json', inventory)
            print(f"✓ Setup: Forced low stock for {test_product['name']}")
            print(f"  Original: {original_stock} → Test: 0")

        # Step 2: Create initial state
        thread_id = f"test-{uuid.uuid4()}"
        initial_state = ProcurementState(
            thread_id=thread_id,
            step="daily_inventory_check",
            status="pending",
            next_action="find_suppliers"  # Force regular procurement path
        )

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        print(f"\n✓ Created workflow with thread_id: {thread_id}")

        # Step 3: Run workflow until it needs human input
        print("\n[Running workflow...]")

        current_state = initial_state
        step_count = 0
        max_steps = 10

        for step_output in workflow_graph.stream(current_state.dict(), config):
            step_count += 1
            print(f"\nStep {step_count}: {list(step_output.keys())}")

            # Get the latest state from the step
            node_name = list(step_output.keys())[0]
            node_state = step_output[node_name]

            print(f"  Status: {node_state.get('status')}")
            print(f"  Step: {node_state.get('step')}")
            print(f"  Message: {node_state.get('message', '')[:100]}")

            current_state = ProcurementState(**node_state)

            # Break if we're waiting for human input
            if current_state.step == "awaiting_human_input":
                print("\n✓ Workflow paused - awaiting human approval")
                break

            if step_count >= max_steps:
                print(f"\n⚠ Reached max steps ({max_steps})")
                break

        # Step 4: Verify workflow state at approval point
        assert current_state.step == "awaiting_human_input", \
            f"Workflow should pause for approval, but step is: {current_state.step}"
        assert current_state.status == "awaiting_approval", \
            f"Status should be awaiting_approval, but is: {current_state.status}"

        print("\n" + "="*80)
        print("VERIFICATION: Workflow State at Approval Point")
        print("="*80)

        # Verify reorder proposals were created
        assert 'reorder_proposals' in current_state.data, \
            "Should have reorder proposals"
        print(f"✓ Reorder proposals: {len(current_state.data['reorder_proposals'])}")

        # Verify suppliers were selected
        assert 'supplier_selections' in current_state.data, \
            "Should have supplier selections"
        print(f"✓ Supplier selections: {len(current_state.data['supplier_selections'])}")

        # Verify draft orders were created
        assert 'draft_orders' in current_state.data, \
            "Should have draft orders"
        draft_orders = current_state.data['draft_orders']
        print(f"✓ Draft orders created: {len(draft_orders)}")

        for i, order in enumerate(draft_orders):
            print(f"\n  Order {i}:")
            print(f"    Supplier: {order['supplier_name']}")
            print(f"    Items: {len(order['items'])}")
            print(f"    Total: €{order['total_amount']:.2f}")

        # Cleanup: Restore original inventory
        if test_inventory:
            test_inventory['quantity_in_stock'] = original_stock
            db.save_json('inventory.json', inventory)
            print(f"\n✓ Cleanup: Restored inventory to {original_stock}")

        print("\n" + "="*80)
        print("✓ INTEGRATION TEST PASSED - Workflow from shortage to approval works!")
        print("="*80)

    def test_workflow_with_approval_and_completion(self, workflow_graph, db, mock_llm):
        """
        Test complete workflow inclusief human approval en order completion
        """
        print("\n" + "="*80)
        print("INTEGRATION TEST: COMPLETE WORKFLOW WITH APPROVAL")
        print("="*80)

        # Setup
        inventory = db.get_inventory()
        products = db.get_products()
        test_product = products[0]
        test_inventory = next(
            (i for i in inventory if i['product_id'] == test_product['product_id']),
            None
        )

        original_stock = test_inventory['quantity_in_stock']
        test_inventory['quantity_in_stock'] = 0
        db.save_json('inventory.json', inventory)

        # Phase 1: Run until approval needed
        thread_id = f"test-approval-{uuid.uuid4()}"
        initial_state = ProcurementState(
            thread_id=thread_id,
            step="daily_inventory_check",
            status="pending",
            next_action="find_suppliers"
        )

        config = {"configurable": {"thread_id": thread_id}}

        print("\n[Phase 1: Running workflow to approval point...]")

        current_state = None
        for step_output in workflow_graph.stream(initial_state.dict(), config):
            node_name = list(step_output.keys())[0]
            node_state = step_output[node_name]
            current_state = ProcurementState(**node_state)

            print(f"  → {node_name}: {current_state.status}")

            if current_state.step == "awaiting_human_input":
                break

        assert current_state is not None, "Workflow should have run"
        assert current_state.step == "awaiting_human_input"
        print("✓ Phase 1 complete - workflow paused for approval")

        # Phase 2: Simulate human approval
        print("\n[Phase 2: Simulating human approval...]")

        draft_orders = current_state.data.get('draft_orders', [])
        assert len(draft_orders) > 0, "Should have draft orders"

        # Approve all orders
        approval_state = ProcurementState(**current_state.dict())
        approval_state.approved_orders = list(range(len(draft_orders)))
        approval_state.approved_by = "test_manager"
        approval_state.approval_decision = "approved"

        print(f"✓ Approving {len(draft_orders)} order(s) as 'test_manager'")

        # Phase 3: Continue workflow with approval
        print("\n[Phase 3: Continuing workflow with approval...]")

        final_state = None
        for step_output in workflow_graph.stream(approval_state.dict(), config):
            node_name = list(step_output.keys())[0]
            node_state = step_output[node_name]
            final_state = ProcurementState(**node_state)

            print(f"  → {node_name}: {final_state.status}")

        # Verify final state
        assert final_state is not None, "Should have final state"
        print(f"\n✓ Final status: {final_state.status}")
        print(f"✓ Final step: {final_state.step}")

        # Verify orders were created
        if 'created_orders' in final_state.data:
            created_orders = final_state.data['created_orders']
            print(f"✓ Created {len(created_orders)} purchase order(s)")

            # Verify in database
            all_orders = db.get_purchase_orders()
            for created in created_orders:
                order_id = created['order_id']
                db_order = next(
                    (o for o in all_orders if o['purchase_order_id'] == order_id),
                    None
                )
                assert db_order is not None, f"Order {order_id} should exist in DB"
                assert db_order['status'] == 'approved', f"Order {order_id} should be approved"
                assert db_order['approved_by'] == 'test_manager'
                print(f"  Order {order_id}: verified in database ✓")

        # Cleanup
        test_inventory['quantity_in_stock'] = original_stock
        db.save_json('inventory.json', inventory)

        print("\n" + "="*80)
        print("✓ INTEGRATION TEST PASSED - Complete workflow with approval!")
        print("="*80)

    def test_workflow_delivery_and_inventory_update(self, workflow_graph, db, mock_llm):
        """
        Test volledige flow: shortage → order → delivery → inventory update
        """
        print("\n" + "="*80)
        print("INTEGRATION TEST: DELIVERY AND INVENTORY UPDATE")
        print("="*80)

        # Setup: Create and approve an order first
        products = db.get_products()
        inventory = db.get_inventory()
        test_product = products[0]
        test_inventory = next(
            (i for i in inventory if i['product_id'] == test_product['product_id']),
            None
        )

        initial_stock = test_inventory['quantity_in_stock']
        print(f"Initial stock: {initial_stock}")

        # Create an approved order with past delivery date
        suppliers = db.get_suppliers_for_product(test_product['product_id'])
        order_quantity = 100

        created_order = db.create_purchase_order(
            supplier_id=suppliers[0]['supplier_id'],
            items=[{
                'product_id': test_product['product_id'],
                'quantity': order_quantity,
                'unit_price': suppliers[0]['price_per_unit']
            }],
            approved_by='test_manager'
        )

        # Set delivery date to past
        orders = db.get_purchase_orders()
        for order in orders:
            if order['purchase_order_id'] == created_order['purchase_order_id']:
                past_date = datetime.now() - timedelta(days=1)
                order['expected_delivery_date'] = past_date.isoformat()
                break
        db.save_json('purchase_order.json', orders)

        print(f"✓ Created order {created_order['purchase_order_id']} with past delivery date")

        # Run workflow starting with delivery processing
        thread_id = f"test-delivery-{uuid.uuid4()}"
        initial_state = ProcurementState(
            thread_id=thread_id,
            step="process_due_deliveries",
            status="pending"
        )

        config = {"configurable": {"thread_id": thread_id}}

        print("\n[Running workflow with delivery processing...]")

        delivery_processed = False
        for step_output in workflow_graph.stream(initial_state.dict(), config):
            node_name = list(step_output.keys())[0]
            print(f"  → {node_name}")

            if node_name == "process_due_deliveries":
                delivery_processed = True

        assert delivery_processed, "Delivery processing node should have run"

        # Verify inventory was updated
        updated_inventory = db.get_inventory()
        updated_test_inventory = next(
            (i for i in updated_inventory if i['product_id'] == test_product['product_id']),
            None
        )

        final_stock = updated_test_inventory['quantity_in_stock']
        stock_increase = final_stock - initial_stock

        print(f"\n✓ Inventory updated:")
        print(f"  Initial: {initial_stock}")
        print(f"  Final: {final_stock}")
        print(f"  Increase: {stock_increase}")

        assert stock_increase == order_quantity, \
            f"Stock should increase by {order_quantity}, but increased by {stock_increase}"

        # Verify order status
        final_orders = db.get_purchase_orders()
        final_order = next(
            (o for o in final_orders if o['purchase_order_id'] == created_order['purchase_order_id']),
            None
        )

        assert final_order['status'] == 'delivered', \
            f"Order should be delivered, but status is {final_order['status']}"
        print(f"✓ Order {created_order['purchase_order_id']} marked as delivered")

        print("\n" + "="*80)
        print("✓ INTEGRATION TEST PASSED - Delivery updates inventory correctly!")
        print("="*80)

    def test_workflow_routing_logic(self, workflow_graph, db, mock_llm):
        """
        Test de routing logic van de workflow graph
        """
        print("\n" + "="*80)
        print("INTEGRATION TEST: WORKFLOW ROUTING LOGIC")
        print("="*80)

        # Test Case 1: Route to find_suppliers when shortage exists
        thread_id = f"test-routing-{uuid.uuid4()}"

        # Force low stock
        inventory = db.get_inventory()
        products = db.get_products()
        test_inventory = next(
            (i for i in inventory if i['product_id'] == products[0]['product_id']),
            None
        )
        original_stock = test_inventory['quantity_in_stock']
        test_inventory['quantity_in_stock'] = 0
        db.save_json('inventory.json', inventory)

        initial_state = ProcurementState(
            thread_id=thread_id,
            step="daily_inventory_check",
            next_action="find_suppliers"
        )

        config = {"configurable": {"thread_id": thread_id}}

        print("\n[Test Case 1: Routing with shortage → find_suppliers]")

        nodes_visited = []
        for step_output in workflow_graph.stream(initial_state.dict(), config):
            node_name = list(step_output.keys())[0]
            nodes_visited.append(node_name)
            print(f"  → {node_name}")

            if len(nodes_visited) > 15:  # Safety limit
                break

        # Verify expected routing
        assert "process_due_deliveries" in nodes_visited, \
            "Should visit process_due_deliveries"
        assert "daily_inventory_check" in nodes_visited, \
            "Should visit daily_inventory_check"
        assert "find_suppliers" in nodes_visited, \
            "Should route to find_suppliers when shortage exists"
        assert "create_purchase_order" in nodes_visited, \
            "Should create purchase order"
        assert "human_approval" in nodes_visited, \
            "Should request human approval"

        print(f"\n✓ Routing verified - visited {len(nodes_visited)} nodes")
        print(f"  Path: {' → '.join(nodes_visited)}")

        # Cleanup
        test_inventory['quantity_in_stock'] = original_stock
        db.save_json('inventory.json', inventory)

        print("\n" + "="*80)
        print("✓ INTEGRATION TEST PASSED - Routing logic works correctly!")
        print("="*80)


if __name__ == '__main__':
    # Run tests with verbose output
    pytest.main([__file__, '-v', '-s'])
