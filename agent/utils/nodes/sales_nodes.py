from datetime import datetime, timedelta

from agent.procurement_data import ProcurementDatabase
from agent.utils.state import ProcurementState


def _detect_price_fluctuations(db: ProcurementDatabase, lookback_days: int = 14, threshold_pct: float = 12.0):
    """Detect significant recent price increases per product."""
    try:
        history = db.get_price_history()
        products = db.get_products()
    except Exception:
        return []

    cutoff = datetime.now().date() - timedelta(days=lookback_days)
    product_names = {p.get('product_id'): p.get('name', 'Unknown') for p in products}

    grouped = {}
    for entry in history:
        product_id = entry.get('product_id')
        price = entry.get('price')
        date_raw = entry.get('date')
        if product_id is None or price is None or not date_raw:
            continue

        try:
            day = datetime.fromisoformat(str(date_raw)).date()
            price_value = float(price)
        except (ValueError, TypeError):
            continue

        if day < cutoff:
            continue
        grouped.setdefault(product_id, []).append((day, price_value))

    alerts = []
    for product_id, points in grouped.items():
        points.sort(key=lambda item: item[0])
        if len(points) < 2:
            continue

        start_price = points[0][1]
        end_price = points[-1][1]
        if start_price <= 0:
            continue

        increase_pct = ((end_price - start_price) / start_price) * 100
        if increase_pct >= threshold_pct:
            alerts.append({
                'product_id': product_id,
                'product_name': product_names.get(product_id, 'Unknown'),
                'start_price': round(start_price, 2),
                'current_price': round(end_price, 2),
                'increase_pct': round(increase_pct, 2),
                'lookback_days': lookback_days,
                'severity': 'high' if increase_pct >= (threshold_pct * 1.5) else 'medium',
            })

    return alerts


def analyse_sales_velocity_node(state: ProcurementState) -> ProcurementState:
    """
    Analyse sales velocity per product and compute dynamic reorder levels.
    This node runs before inventory checks so fast-selling products are reordered earlier.
    """
    db = ProcurementDatabase()

    try:
        inventory = db.get_inventory()
        products = db.get_products()
        velocity_by_product = db.get_sales_velocity_by_product(window_days=30)
    except Exception as e:
        state.errors.append(f"Failed to analyze sales velocity: {str(e)}")
        state.message = "Fout bij analyse van verkoopsnelheid."
        state.status = "error"
        return state

    inventory_by_product = {item.get('product_id'): item for item in inventory}
    products_by_id = {item.get('product_id'): item for item in products}

    dynamic_reorder_levels = {}
    velocity_forecasts = []
    alerts = []

    for product_id, velocity_data in velocity_by_product.items():
        inv_item = inventory_by_product.get(product_id)
        product = products_by_id.get(product_id)

        if not inv_item or not product:
            continue

        qty_in_stock = int(inv_item.get('quantity_in_stock', 0) or 0)
        static_reorder_level = int(inv_item.get('reorder_level', 0) or 0)
        velocity_per_day = float(velocity_data.get('velocity_per_day', 0.0) or 0.0)

        if velocity_per_day <= 0:
            dynamic_reorder_levels[str(product_id)] = static_reorder_level
            continue

        # Policy: fast movers receive a stronger lead-time and safety buffer.
        if velocity_per_day >= 4:
            lead_time_days = 10
            safety_stock_days = 7
        elif velocity_per_day >= 2:
            lead_time_days = 8
            safety_stock_days = 5
        else:
            lead_time_days = 7
            safety_stock_days = 3
        safety_stock_qty = round(velocity_per_day * safety_stock_days)
        demand_during_lead_time = round(velocity_per_day * lead_time_days)

        dynamic_reorder_level = max(
            static_reorder_level,
            demand_during_lead_time + safety_stock_qty,
        )
        dynamic_reorder_levels[str(product_id)] = dynamic_reorder_level

        days_until_stockout = qty_in_stock / velocity_per_day if velocity_per_day > 0 else None
        predicted_stockout_date = None
        if days_until_stockout is not None:
            predicted_stockout_date = (datetime.now() + timedelta(days=days_until_stockout)).date().isoformat()

        reorder_recommended = days_until_stockout is not None and days_until_stockout <= (lead_time_days + safety_stock_days)

        forecast = {
            'product_id': product_id,
            'product_name': product.get('name', 'Unknown'),
            'current_stock': qty_in_stock,
            'static_reorder_level': static_reorder_level,
            'dynamic_reorder_level': dynamic_reorder_level,
            'reorder_basis': 'sales_velocity_plus_safety_stock',
            'velocity_per_day': velocity_per_day,
            'velocity_per_week': velocity_data.get('velocity_per_week', 0.0),
            'predicted_stockout_date': predicted_stockout_date,
            'days_until_stockout': round(days_until_stockout, 2) if days_until_stockout is not None else None,
            'lead_time_days': lead_time_days,
            'safety_stock_days': safety_stock_days,
            'reorder_recommended': reorder_recommended,
        }
        velocity_forecasts.append(forecast)

        if reorder_recommended:
            alerts.append(
                f"Hoge verkoopsnelheid: {forecast['product_name']} ({velocity_per_day:.2f}/dag), stockout rond {predicted_stockout_date}."
            )

    state.data['dynamic_reorder_levels'] = dynamic_reorder_levels
    state.data['sales_velocity_forecasts'] = velocity_forecasts
    state.sales_velocity_alerts = alerts

    price_alerts = _detect_price_fluctuations(db)
    state.data['price_fluctuation_alerts'] = price_alerts

    if alerts:
        state.message = f"Sales velocity geanalyseerd. {len(alerts)} product(en) hebben versnelde reorder nodig."
        state.status = "attention"
    else:
        state.message = "Sales velocity geanalyseerd. Geen urgente versnelde reorder gevonden."

    if price_alerts:
        state.status = "attention"
        state.message += f" Waarschuwing: {len(price_alerts)} product(en) met significante prijsstijging."

    return state
