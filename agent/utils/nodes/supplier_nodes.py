from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.utils.memory import get_last_rejection_reason, get_recent_rejections
from langchain_google_genai import ChatGoogleGenerativeAI
import os

db = ProcurementDatabase()

def find_suppliers_node(state: ProcurementState) -> ProcurementState:
    print("🔍 DEBUG: find_suppliers_node aangeroepen!")
    print(f"   - step: {getattr(state, 'step', 'N/A')}")
    print(f"   - status: {getattr(state, 'status', 'N/A')}")
    print(f"   - path_choice: {getattr(state, 'path_choice', 'N/A')}")
    
    # Initialiseer LLM pas binnen de functie zodat de env key altijd beschikbaar is en mocking mogelijk blijft
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-pro-preview",
        temperature=0.2,
        api_key=os.getenv("GOOGLE_API_KEY")
    )

    proposals = state.data.get('reorder_proposals', [])
    deduped_proposals = []
    seen_keys = set()
    for proposal in proposals:
        key = (
            proposal.get('product_id'),
            str(proposal.get('product_code', '')).strip().lower(),
            str(proposal.get('product_name', '')).strip().lower(),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_proposals.append(proposal)

    # In de samengevoegde flow kan dit node ook draaien met alleen new-release orders.
    if not proposals:
        state.data['supplier_selections'] = []
        state.message = (
            "Geen voorraden onder minimum gevonden voor reorder. "
            "Door naar orderopbouw voor eventuele new releases."
        )
        state.status = "ok"
        state.step = "create_purchase_order"
        return state

    # Clear supplier path data to prevent mixing
    state.clear_path_data("suppliers")

    products = db.get_products()
    product_map_by_sku = {}
    product_map_by_name = {}
    for product in products:
        sku = product.get('sku')
        if sku:
            product_map_by_sku[sku] = product

        name = product.get('name')
        if name:
            product_map_by_name[name.strip().lower()] = product

    supplier_selections = []

    for proposal in deduped_proposals:
        product_code = proposal.get('product_code')
        product_name = proposal.get('product_name')

        product = None
        if product_code and product_code != 'N/A':
            product = product_map_by_sku.get(product_code)
        if not product and product_name:
            product = product_map_by_name.get(product_name.strip().lower())

        if not product:
            continue

        product_id = proposal.get('product_id') or product.get('product_id')
        if product_id is None:
            continue

        # Get suppliers for this product
        supplier_options = db.get_suppliers_for_product(product_id)

        if not supplier_options:
            continue

        # Remove accidental duplicate suppliers to keep output stable and readable.
        unique_options = []
        seen_supplier_ids = set()
        for option in supplier_options:
            sid = option.get('supplier_id')
            if sid in seen_supplier_ids:
                continue
            seen_supplier_ids.add(sid)
            unique_options.append(option)
        supplier_options = unique_options

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

            rejection_reason = get_last_rejection_reason(opt['supplier_id'])
            recent_rejections = get_recent_rejections(opt['supplier_id'], days=7)

            if rejection_reason:
                analysis_prompt += f"\n   - Laatste afkeuring: {rejection_reason}"
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
            'product_name': product_name,
            'product_id': product_id,
            'category': proposal.get('category') or product.get('category', 'Unknown'),
            'source_type': proposal.get('source_type', 'inventory_low_stock'),
            'reorder_qty': proposal.get('reorder_qty', 0),
            'selected_supplier': recommended_supplier,
            'all_options': supplier_options,
            'ai_recommendation': recommendation,
            'ai_recommendation_summary': (
                f"{product_name}: beste match is {recommended_supplier.get('supplier_name', 'Onbekend')} "
                f"voor {proposal.get('reorder_qty', 0)} stuks."
            )
        })

    state.data['supplier_selections'] = supplier_selections

    # Update UI helper fields
    state.supplier_offers = []
    for selection in supplier_selections:
        for option in selection.get('all_options', []):
            state.supplier_offers.append({
                **option,
                'product_name': selection['product_name'],
                'category': selection['category'],
                'source_type': selection['source_type']
            })

    if supplier_selections:
        summary = "\n".join([
            f"- {s['product_name']} ({s.get('category', 'Unknown')}): {s['selected_supplier'].get('supplier_name', 'Onbekend')}"
            for s in supplier_selections
        ])
        state.message = f"Leveranciers geselecteerd voor {len(supplier_selections)} producten.\n{summary}"
        state.status = "suppliers_selected"
    else:
        state.message = "Geen geschikte leveranciers gevonden voor de geselecteerde records."
        state.status = "no_suppliers_found"

    state.step = "create_purchase_order"

    return state
