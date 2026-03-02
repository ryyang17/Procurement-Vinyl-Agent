"""
Business Logic Layer - Nodes for the procurement workflow
Maps to requirements R1-R11
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from agent.database import ProcurementDatabase

db = ProcurementDatabase()


# ==================== STATE MODELS ====================

class ProcurementState(BaseModel):
    """Main state model for the procurement workflow"""
    step: str = "daily_inventory_check"  # Current step in workflow
    status: str = "pending"  # pending, processing, awaiting_approval, completed, error
    message: str = ""
    data: Dict[str, Any] = {}
    errors: list[str] = []

    class Config:
        arbitrary_types_allowed = True


class ReorderProposal(BaseModel):
    """Model for reorder proposal"""
    product_code: str
    product_name: str
    current_qty: int
    reorder_qty: int
    min_threshold: int


class SupplierOption(BaseModel):
    """Model for supplier comparison"""
    supplier_id: int
    supplier_name: str
    product_code: str
    price_per_unit: float
    lead_time_days: int
    late_deliveries_count: int
    quality_rating: float


# ==================== NODE 1: DAILY INVENTORY CHECK (R1) ====================

def daily_inventory_check_node(state: ProcurementState) -> ProcurementState:
    """
    R1: Agent checks inventory daily
    R2: If stock under minimum, generate purchase proposal
    R3: Reorder quantity depends on current stock
    """
    try:
        # Perform daily inventory check
        check_result = db.daily_inventory_check()

        items_below_threshold = check_result['items_below_threshold']

        if not items_below_threshold:
            state.status = "completed"
            state.message = f"✓ Inventory check completed. All {check_result['total_checked']} items above reorder point."
            state.data = check_result
            return state

        # Generate reorder proposals for items below threshold
        proposals = []
        for item in items_below_threshold:
            # R3: Calculate reorder quantity based on inventory
            # Strategy: Reorder to max_capacity
            reorder_qty = item['max_capacity'] - item['current_qty']

            proposal = db.generate_reorder_proposal(
                product_code=item['product_code'],
                reorder_qty=reorder_qty
            )

            proposals.append({
                'product_code': item['product_code'],
                'product_name': item['product_name'],
                'current_qty': item['current_qty'],
                'reorder_qty': reorder_qty,
                'min_threshold': item['min_threshold']
            })

        state.status = "processing"
        state.message = f"⚠ Found {len(proposals)} items below reorder point. Proposals generated."
        state.data = {
            'proposals': proposals,
            'total_checked': check_result['total_checked']
        }

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error in inventory check: {str(e)}")
        state.message = f"❌ Inventory check failed: {str(e)}"

    return state


# ==================== NODE 2: FIND SUPPLIERS (R4) ====================

def find_suppliers_node(state: ProcurementState) -> ProcurementState:
    """
    R4: Agent finds and compares up to 3 suppliers
    R5: Cheapest supplier with acceptable lead time is suggested
    """
    try:
        if not state.data.get('proposals'):
            state.message = "No proposals to process"
            return state

        # Take first proposal to work with
        proposal = state.data['proposals'][0]
        product_code = proposal['product_code']

        # Find suppliers (limited to 3)
        suppliers = db.find_suppliers_for_product(product_code, limit=3)

        if not suppliers:
            state.status = "error"
            state.errors.append(f"No suppliers found for {product_code}")
            state.message = f"❌ No suppliers available for {product_code}"
            return state

        # Score suppliers: price (70%) + lead time (20%) + quality (10%)
        scored_suppliers = []
        for supplier in suppliers:
            # Normalize scores
            price_score = 100 - (supplier['price_per_unit'] / max([s['price_per_unit'] for s in suppliers]) * 100)
            lead_time_score = 100 - (supplier['avg_lead_time_days'] / 30 * 100)  # Penalize long lead times
            quality_score = supplier['quality_rating'] * 20  # 0-100 scale

            total_score = (price_score * 0.7) + (lead_time_score * 0.2) + (quality_score * 0.1)

            scored_suppliers.append({
                'supplier_id': supplier['supplier_id'],
                'supplier_name': supplier['supplier_name'],
                'product_code': product_code,
                'price_per_unit': supplier['price_per_unit'],
                'lead_time_days': supplier['avg_lead_time_days'],
                'late_deliveries_count': supplier['late_deliveries_count'],
                'quality_rating': supplier['quality_rating'],
                'score': total_score
            })

        # Sort by score descending
        scored_suppliers.sort(key=lambda x: x['score'], reverse=True)

        # Select best supplier
        best_supplier = scored_suppliers[0]

        state.status = "processing"
        state.message = f"✓ Found {len(suppliers)} suppliers. Best option: {best_supplier['supplier_name']} (Score: {best_supplier['score']:.1f})"
        state.data['selected_supplier'] = best_supplier
        state.data['proposal'] = proposal
        state.data['all_supplier_options'] = scored_suppliers

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error finding suppliers: {str(e)}")
        state.message = f"❌ Supplier search failed: {str(e)}"

    return state


# ==================== NODE 3: CREATE PURCHASE ORDER (R6-R8) ====================

def create_purchase_order_node(state: ProcurementState) -> ProcurementState:
    """
    R6: Create purchase order (awaiting approval)
    R7: Show supplier, quantity, price
    R8: Order only placed after human approval
    """
    try:
        if not state.data.get('selected_supplier'):
            state.status = "error"
            state.errors.append("No supplier selected")
            return state

        supplier = state.data['selected_supplier']
        proposal = state.data['proposal']

        # Create pending purchase order
        order = db.create_purchase_order(
            supplier_id=supplier['supplier_id'],
            product_code=proposal['product_code'],
            quantity=proposal['reorder_qty'],
            unit_price=supplier['price_per_unit'],
            expected_delivery_date=None  # Will be set during approval
        )

        state.status = "awaiting_approval"
        state.message = f"✓ Purchase order created: {order['order_number']} (PENDING APPROVAL)"
        state.data['order'] = order
        state.data['awaiting_approval'] = {
            'order_id': order['order_id'],
            'order_number': order['order_number'],
            'supplier_name': supplier['supplier_name'],
            'product_code': proposal['product_code'],
            'quantity': proposal['reorder_qty'],
            'unit_price': supplier['price_per_unit'],
            'total_cost': order['total_cost'],
            'created_at': datetime.now().isoformat()
        }

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error creating purchase order: {str(e)}")
        state.message = f"❌ Order creation failed: {str(e)}"

    return state


# ==================== NODE 4: HUMAN APPROVAL (R6-R8) ====================

def human_approval_node(state: ProcurementState, approved: bool = False, approved_by: str = "system") -> ProcurementState:
    """
    R6: Human must approve each order
    R7: Show supplier, quantity, total price
    R8: Order only placed after approval
    """
    try:
        if not state.data.get('order'):
            state.status = "error"
            state.errors.append("No order to approve")
            return state

        order = state.data['order']
        order_id = order['order_id']

        if approved:
            # Approve the order
            db.approve_purchase_order(order_id, approved_by)
            state.status = "completed"
            state.message = f"✓ Order {order['order_number']} approved and placed!"
            state.data['approved_order'] = {
                'order_id': order_id,
                'order_number': order['order_number'],
                'status': 'approved',
                'approved_by': approved_by,
                'approved_at': datetime.now().isoformat()
            }
        else:
            # Reject the order
            db.reject_purchase_order(order_id, approved_by)
            state.status = "completed"
            state.message = f"✗ Order {order['order_number']} rejected"
            state.data['rejected_order'] = {
                'order_id': order_id,
                'order_number': order['order_number'],
                'status': 'rejected',
                'rejected_by': approved_by
            }

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error in approval process: {str(e)}")
        state.message = f"❌ Approval process failed: {str(e)}"

    return state


# ==================== NODE 5: INVOICE VERIFICATION (R9-R10) ====================

def verify_invoice_node(state: ProcurementState, invoice_number: str,
                       invoice_amount: float, invoice_quantity: int,
                       supplier_id: int, order_id: int) -> ProcurementState:
    """
    R9: Agent compares invoice with purchase order
    R10: Alert on price or quantity discrepancies
    """
    try:
        # Create invoice and check for discrepancies
        invoice_result = db.create_invoice(
            invoice_number=invoice_number,
            order_id=order_id,
            supplier_id=supplier_id,
            invoice_amount=invoice_amount,
            invoice_quantity=invoice_quantity
        )

        if 'error' in invoice_result:
            state.status = "error"
            state.errors.append(invoice_result['error'])
            state.message = f"❌ Invoice verification failed: {invoice_result['error']}"
            return state

        state.data['invoice'] = invoice_result

        if invoice_result['discrepancy_type']:
            state.status = "awaiting_approval"
            state.message = f"⚠ Invoice {invoice_number} has discrepancies: {invoice_result['discrepancy_type']}"
            state.data['invoice_discrepancy'] = {
                'invoice_id': invoice_result['invoice_id'],
                'discrepancy_type': invoice_result['discrepancy_type'],
                'message': invoice_result['discrepancy_message']
            }
        else:
            state.status = "completed"
            state.message = f"✓ Invoice {invoice_number} verified successfully"

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error verifying invoice: {str(e)}")
        state.message = f"❌ Invoice verification failed: {str(e)}"

    return state


# ==================== NODE 6: SUPPLIER HISTORY TRACKING (R11) ====================

def update_supplier_history_node(state: ProcurementState,
                                supplier_id: int,
                                is_late: bool = False,
                                latest_price: Optional[float] = None) -> ProcurementState:
    """
    R11: Track supplier history
    - Last price paid
    - Number of late deliveries
    """
    try:
        if is_late:
            db.update_supplier_late_delivery(supplier_id)
            state.message = f"✓ Supplier late delivery recorded"

        if latest_price:
            db.update_supplier_last_price(supplier_id, latest_price)
            state.message = f"✓ Supplier price history updated: €{latest_price}"

        state.data['supplier_history_updated'] = True
        state.status = "completed"

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error updating supplier history: {str(e)}")
        state.message = f"❌ Supplier history update failed: {str(e)}"

    return state


# ==================== ROUTING / DECISION FUNCTIONS ====================

def should_generate_proposals(state: ProcurementState) -> bool:
    """Check if proposals were generated in inventory check"""
    return state.data.get('proposals') and len(state.data['proposals']) > 0


def has_invoice_discrepancy(state: ProcurementState) -> bool:
    """Check if invoice has discrepancies"""
    return state.data.get('invoice_discrepancy') is not None


def get_pending_approvals() -> Dict[str, Any]:
    """Get all pending orders awaiting approval"""
    pending_orders = db.get_pending_orders()
    return {
        'count': len(pending_orders),
        'orders': pending_orders
    }


def get_pending_invoices() -> Dict[str, Any]:
    """Get all invoices with discrepancies"""
    pending_invoices = db.get_pending_invoice_verification()
    return {
        'count': len(pending_invoices),
        'invoices': pending_invoices
    }

