from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase

db = ProcurementDatabase()

def process_due_deliveries_node(state: ProcurementState) -> ProcurementState:

    processed_deliveries = db.process_due_deliveries()

    if processed_deliveries:
        # Log what was processed
        total_orders = len(processed_deliveries)
        total_products = sum(len(delivery['updated_products']) for delivery in processed_deliveries)

        delivery_summary = []
        for delivery in processed_deliveries:
            order_id = delivery['order_id']
            products = delivery['updated_products']
            product_names = [p['product_name'] for p in products]
            delivery_summary.append(f"Order #{order_id}: {', '.join(product_names)}")

        state.data['processed_deliveries'] = processed_deliveries
        state.message = f"Leveringen verwerkt: {total_orders} bestellingen, {total_products} producten bijgewerkt. " + "; ".join(delivery_summary)
    else:
        state.message = "Geen leveringen te verwerken vandaag."

    return state
