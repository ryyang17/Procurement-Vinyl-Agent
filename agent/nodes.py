"""
Business Logic Layer - Nodes for the procurement workflow
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from data import ProcurementDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
import json

db = ProcurementDatabase()

# Lazy LLM initialization function
_llm_instance = None

def get_llm():
    """Get or create LLM instance"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.3,
            max_tokens=1500
        )
    return _llm_instance


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
    R1: Agent checks inventory daily with LLM intelligence
    R2: If stock under minimum, generate purchase proposal
    R3: Reorder quantity depends on current stock, sales velocity, and lead time
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

        # Generate reorder proposals for items below threshold with LLM analysis
        proposals = []
        llm_insights = []

        for item in items_below_threshold:
            # Get historical context from memory
            past_decisions = db.get_agent_memory(
                context_type='inventory_analysis',
                product_code=item['product_code'],
                limit=3
            )

            # Prepare context for LLM
            context = {
                'product': item['product_name'],
                'product_code': item['product_code'],
                'current_qty': item['current_qty'],
                'min_threshold': item['min_threshold'],
                'max_capacity': item['max_capacity'],
                'avg_daily_sales': item['avg_daily_sales'],
                'lead_time_days': item['lead_time_days'],
                'sales_trend': item['sales_trend'],
                'days_until_stockout': item['days_until_stockout'],
                'expected_stockout_date': str(item['expected_stockout_date']) if item['expected_stockout_date'] else 'Unknown'
            }

            # Get LLM recommendation for reorder quantity
            system_prompt = """Je bent een AI Procurement Expert voor vinyl producten.
            
Analyseer de voorraadsituatie en geef advies over:
1. De urgentie van de bestelling
2. De optimale bestelhoeveelheid (rekening houdend met verkooptempo, levertijd en safety stock)
3. Risico's en aanbevelingen

Antwoord in JSON formaat met keys: 'urgency_level' (low/medium/high/critical), 'recommended_qty', 'reasoning'"""

            human_prompt = f"""Voorraadsituatie voor {context['product']}:
- Huidige voorraad: {context['current_qty']} stuks
- Minimale drempel: {context['min_threshold']} stuks
- Maximale capaciteit: {context['max_capacity']} stuks
- Gemiddelde dagelijkse verkoop: {context['avg_daily_sales']:.1f} stuks
- Levertijd leverancier: {context['lead_time_days']} dagen
- Verkoop trend: {context['sales_trend']}
- Dagen tot uitverkocht: {context['days_until_stockout']}
- Verwachte uitverkoop datum: {context['expected_stockout_date']}

Geef je aanbeveling voor de bestelhoeveelheid."""

            try:
                llm_response = get_llm().invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ])

                # Parse LLM response
                llm_advice = llm_response.content

                # Try to extract JSON if present
                try:
                    import re
                    json_match = re.search(r'\{.*\}', llm_advice, re.DOTALL)
                    if json_match:
                        llm_data = json.loads(json_match.group())
                        recommended_qty = llm_data.get('recommended_qty', item['max_capacity'] - item['current_qty'])
                        reasoning = llm_data.get('reasoning', llm_advice)
                    else:
                        recommended_qty = item['max_capacity'] - item['current_qty']
                        reasoning = llm_advice
                except:
                    recommended_qty = item['max_capacity'] - item['current_qty']
                    reasoning = llm_advice

                llm_insights.append({
                    'product_code': item['product_code'],
                    'llm_analysis': llm_advice
                })

                # Store in memory
                db.store_agent_memory(
                    context_type='inventory_analysis',
                    product_code=item['product_code'],
                    decision_context=json.dumps(context),
                    llm_reasoning=llm_advice,
                    confidence_score=0.85
                )

            except Exception as llm_error:
                print(f"   [LLM Warning] {llm_error}, using fallback calculation")
                recommended_qty = item['max_capacity'] - item['current_qty']
                reasoning = f"Fallback: Reorder to max capacity based on {item['days_until_stockout']} days until stockout"
                llm_advice = None

            # R3: Calculate reorder quantity based on LLM recommendation
            reorder_qty = recommended_qty

            proposal = db.generate_reorder_proposal(
                product_code=item['product_code'],
                reorder_qty=reorder_qty,
                reasoning=reasoning,
                llm_analysis=llm_advice
            )

            proposals.append({
                'product_code': item['product_code'],
                'product_name': item['product_name'],
                'current_qty': item['current_qty'],
                'reorder_qty': reorder_qty,
                'min_threshold': item['min_threshold'],
                'days_until_stockout': item['days_until_stockout'],
                'sales_trend': item['sales_trend'],
                'llm_reasoning': reasoning
            })

        state.status = "processing"
        state.message = f"⚠ Found {len(proposals)} items below reorder point. AI-powered proposals generated."
        state.data = {
            'proposals': proposals,
            'total_checked': check_result['total_checked'],
            'llm_insights': llm_insights
        }

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error in inventory check: {str(e)}")
        state.message = f"❌ Inventory check failed: {str(e)}"

    return state


# ==================== NODE 2: FIND SUPPLIERS (R4) ====================

def find_suppliers_node(state: ProcurementState) -> ProcurementState:
    """
    R4: Agent finds and compares up to 3 suppliers with LLM analysis
    R5: Best supplier is selected based on AI recommendation considering price, lead time, and quality
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
                'score': total_score,
                'min_order_qty': supplier['min_order_qty'],
                'packaging_unit': supplier['packaging_unit']
            })

        # Sort by score descending
        scored_suppliers.sort(key=lambda x: x['score'], reverse=True)

        # Get LLM analysis for supplier selection
        llm_supplier_analysis = None
        try:
            # Get past supplier performance from memory
            supplier_history = []
            for supplier in scored_suppliers[:3]:
                history = db.get_agent_memory(
                    context_type='supplier_performance',
                    supplier_id=supplier['supplier_id'],
                    limit=2
                )
                if history:
                    supplier_history.append({
                        'supplier_name': supplier['supplier_name'],
                        'past_context': [h['decision_context'] for h in history]
                    })

            # Prepare supplier comparison for LLM
            supplier_comparison = "\n".join([
                f"{i+1}. {s['supplier_name']}: €{s['price_per_unit']:.2f}/stuk, {s['lead_time_days']} dagen levertijd, "
                f"Kwaliteit: {s['quality_rating']:.1f}/5, Te laat: {s['late_deliveries_count']}x, "
                f"Min bestelling: {s['min_order_qty']}"
                for i, s in enumerate(scored_suppliers)
            ])

            system_prompt = """Je bent een AI Procurement Expert die leveranciers evalueert.

Analyseer de leveranciers en geef advies over:
1. Welke leverancier is het beste voor deze bestelling?
2. Waarom is deze leverancier de beste keuze?
3. Zijn er risico's of aandachtspunten?

Focus op: totale kosten, leverbetrouwbaarheid, kwaliteit, en minimale bestelhoeveelheden."""

            human_prompt = f"""Product: {proposal['product_name']} ({product_code})
Benodigde hoeveelheid: {proposal['reorder_qty']} stuks
Urgentie: {proposal.get('days_until_stockout', 'Unknown')} dagen tot uitverkocht

Beschikbare leveranciers:
{supplier_comparison}

Welke leverancier raad je aan en waarom?"""

            llm_response = get_llm().invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])

            llm_supplier_analysis = llm_response.content

            # Store in memory
            db.store_agent_memory(
                context_type='supplier_selection',
                product_code=product_code,
                decision_context=json.dumps({
                    'suppliers': scored_suppliers,
                    'quantity_needed': proposal['reorder_qty']
                }),
                llm_reasoning=llm_supplier_analysis,
                confidence_score=0.9
            )

        except Exception as llm_error:
            print(f"   [LLM Warning] Supplier analysis failed: {llm_error}")

        # Select best supplier
        best_supplier = scored_suppliers[0]

        # Adjust quantity to meet minimum order requirements
        adjusted_qty = proposal['reorder_qty']
        if adjusted_qty < best_supplier['min_order_qty']:
            adjusted_qty = best_supplier['min_order_qty']

        # Round up to packaging units
        if best_supplier['packaging_unit'] > 1:
            adjusted_qty = ((adjusted_qty + best_supplier['packaging_unit'] - 1)
                           // best_supplier['packaging_unit']) * best_supplier['packaging_unit']

        state.status = "processing"
        state.message = f"✓ Found {len(suppliers)} suppliers. AI recommends: {best_supplier['supplier_name']} (Score: {best_supplier['score']:.1f})"
        state.data['selected_supplier'] = best_supplier
        state.data['proposal'] = proposal
        state.data['proposal']['reorder_qty'] = adjusted_qty  # Update with adjusted quantity
        state.data['all_supplier_options'] = scored_suppliers
        state.data['llm_supplier_analysis'] = llm_supplier_analysis

    except Exception as e:
        state.status = "error"
        state.errors.append(f"Error finding suppliers: {str(e)}")
        state.message = f"❌ Supplier search failed: {str(e)}"

    return state


# ==================== NODE 3: CREATE PURCHASE ORDER (R6-R8) ====================

def create_purchase_order_node(state: ProcurementState) -> ProcurementState:
    """
    R6: Create purchase order (awaiting approval) with LLM-generated approval recommendation
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

        # Generate LLM approval recommendation
        llm_approval_message = None
        try:
            total_cost = proposal['reorder_qty'] * supplier['price_per_unit']

            system_prompt = """Je bent een AI Procurement Advisor die managers helpt bij goedkeuringsbeslissingen.

Genereer een beknopte goedkeuringsaanbeveling met:
1. Een duidelijke samenvatting van de bestelling
2. Waarom deze bestelling nu nodig is
3. Of goedkeuring wordt aanbevolen (ja/nee) en waarom

Wees professioneel en beknopt."""

            human_prompt = f"""Goedkeuringsverzoek voor inkooporder:

Product: {proposal['product_name']} ({proposal['product_code']})
Leverancier: {supplier['supplier_name']}
Hoeveelheid: {proposal['reorder_qty']} stuks
Prijs per stuk: €{supplier['price_per_unit']:.2f}
Totale kosten: €{total_cost:.2f}
Levertijd: {supplier['lead_time_days']} dagen

Voorraadsituatie:
- Huidige voorraad: {proposal['current_qty']} stuks
- Dagen tot uitverkocht: {proposal.get('days_until_stockout', 'Unknown')}
- Verkoop trend: {proposal.get('sales_trend', 'Unknown')}

Leverancier prestaties:
- Kwaliteitsrating: {supplier['quality_rating']:.1f}/5
- Aantal te late leveringen: {supplier['late_deliveries_count']}

Genereer een goedkeuringsaanbeveling voor de manager."""

            llm_response = get_llm().invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])

            llm_approval_message = llm_response.content

            # Store in memory
            db.store_agent_memory(
                context_type='approval_recommendation',
                product_code=proposal['product_code'],
                supplier_id=supplier['supplier_id'],
                decision_context=json.dumps({
                    'order_details': {
                        'product': proposal['product_name'],
                        'quantity': proposal['reorder_qty'],
                        'total_cost': total_cost
                    }
                }),
                llm_reasoning=llm_approval_message,
                confidence_score=0.88
            )

        except Exception as llm_error:
            print(f"   [LLM Warning] Approval message generation failed: {llm_error}")

        # Create pending purchase order with LLM analysis
        order = db.create_purchase_order(
            supplier_id=supplier['supplier_id'],
            product_code=proposal['product_code'],
            quantity=proposal['reorder_qty'],
            unit_price=supplier['price_per_unit'],
            expected_delivery_date=None,
            llm_analysis=llm_approval_message
        )

        state.status = "awaiting_approval"
        state.message = f"✓ Purchase order created: {order['order_number']} (PENDING APPROVAL)"
        state.data['order'] = order
        state.data['llm_approval_message'] = llm_approval_message
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

