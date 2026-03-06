from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.utils.memory import get_last_rejection_reason, get_recent_rejections
from langchain_google_genai import ChatGoogleGenerativeAI

db = ProcurementDatabase()
llm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0.7)

def find_suppliers_node(state: ProcurementState) -> ProcurementState:

    proposals = state.data.get('reorder_proposals', [])
    if not proposals:
        state.message = "Geen reorder voorstellen om leveranciers voor te zoeken."
        state.step = "complete"
        return state

    products = db.get_products()
    product_map = {p['sku']: p for p in products}

    supplier_selections = []

    for proposal in proposals:
        product_code = proposal['product_code']
        product = product_map.get(product_code)

        if not product:
            continue

        # Get suppliers for this product
        supplier_options = db.get_suppliers_for_product(product['product_id'])

        if not supplier_options:
            continue

        # Limit to top 3 suppliers
        supplier_options = supplier_options[:3]

        # Use LLM to analyze and select best supplier
        analysis_prompt = f"""
            Je bent een procurement specialist voor een vinyl platenwinkel.
            
            Product: {proposal['product_name']} ({product_code})
            Hoeveelheid nodig: {proposal['reorder_qty']} stuks
            
            Beschikbare leveranciers:
            """
        for i, opt in enumerate(supplier_options, 1):
            analysis_prompt += f"\n{i}. {opt['supplier_name']}"
            analysis_prompt += f"\n   - Prijs per unit: €{opt['price_per_unit']:.2f}"
            analysis_prompt += f"\n   - Levertijd: {opt['lead_time_days']} dagen"
            analysis_prompt += f"\n   - Late leveringen: {opt['late_deliveries_count']}"
            analysis_prompt += f"\n   - Kwaliteitsbeoordeling: {opt['quality_rating']}/10"

            # Check for recent rejection history
            rejection_reason = get_last_rejection_reason(opt['supplier_id'])
            if rejection_reason:
                analysis_prompt += f"\n   - ⚠️ WAARSCHUWING: Recent afgekeurd wegens: {rejection_reason}"

            recent_rejections = get_recent_rejections(opt['supplier_id'], days=7)
            if recent_rejections:
                analysis_prompt += f"\n   - {len(recent_rejections)} afkeuring(en) in afgelopen week"

        analysis_prompt += """\n\nSelecteer de beste leverancier op basis van:
            1. Prijs (totale kosten)
            2. Levertijd
            3. Betrouwbaarheid (late leveringen)
            4. Kwaliteit
            5. BELANGRIJK: Let op waarschuwingen over recente afkeuringen!
            
            Geef je aanbeveling in dit formaat:
            LEVERANCIER: [naam]
            REDEN: [korte uitleg waarom deze leverancier het beste is]"""

        response = llm.invoke(analysis_prompt)
        recommendation = response.content

        # Ensure recommendation is a string
        if isinstance(recommendation, list):
            recommendation = ' '.join(str(item) for item in recommendation)
        else:
            recommendation = str(recommendation)

        # Extract recommended supplier
        recommended_supplier = None
        for opt in supplier_options:
            if opt['supplier_name'].lower() in recommendation.lower():
                recommended_supplier = opt
                break

        if not recommended_supplier:
            recommended_supplier = supplier_options[0]  # Default to first

        supplier_selections.append({
            'product_code': product_code,
            'product_name': proposal['product_name'],
            'product_id': product['product_id'],
            'reorder_qty': proposal['reorder_qty'],
            'selected_supplier': recommended_supplier,
            'all_options': supplier_options,
            'ai_recommendation': recommendation
        })

    state.data['supplier_selections'] = supplier_selections
    state.message = f"Leveranciers geselecteerd voor {len(supplier_selections)} producten."
    state.step = "create_purchase_order"
    state.status = "suppliers_selected"

    return state
