from agent.utils.state import ProcurementState
from agent.procurement_data import ProcurementDatabase
from agent.utils.memory import get_last_rejection_reason, get_recent_rejections
from langchain_google_genai import ChatGoogleGenerativeAI
import json
import os

db = ProcurementDatabase()


def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _choose_fallback_supplier(options):
    # Deterministic fallback keeps runtime fast and output stable when LLM output is malformed.
    return min(
        options,
        key=lambda o: (
            float(o.get("price_per_unit", 10**9)),
            int(o.get("lead_time_days", 10**9)),
            int(o.get("late_deliveries_count", 10**9)),
            -float(o.get("quality_rating", 0.0)),
        ),
    )


def _product_key(value) -> str:
    return str(value).strip()


def _build_supplier_reason(option: dict) -> str:
    return (
        f"Beste keuze op basis van prijs (€{option.get('price_per_unit', 0):.2f}), "
        f"levertijd ({option.get('lead_time_days', '?')} dagen), "
        f"betrouwbaarheid ({option.get('late_deliveries_count', '?')} te late leveringen) "
        f"en kwaliteit ({option.get('quality_rating', '?')}/10)."
    )


def _compact_text(value, max_len: int = 80) -> str:
    text = str(value or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."

def find_suppliers_node(state: ProcurementState) -> ProcurementState:
    print("DEBUG: find_suppliers_node called")
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

        supplier_selections.append({
            'product_code': product_code,
            'product_name': product_name,
            'product_id': product_id,
            'category': proposal.get('category') or product.get('category', 'Unknown'),
            'source_type': proposal.get('source_type', 'inventory_low_stock'),
            'reorder_qty': proposal.get('reorder_qty', 0),
            'all_options': supplier_options,
            'selected_supplier': None,
            'ai_recommendation': "",
            'ai_recommendation_summary': "",
        })

    # Build one batched prompt for all proposals to avoid one network call per product.
    recommendation_by_product = {}
    if supplier_selections:
        rejection_cache = {}
        recent_rejection_count_cache = {}
        batched_lines = [
            "Rol: procurement specialist voor vinyl retail.",
            "Taak: kies exact 1 leverancier per product.",
            "Optimaliseer op: lage prijs, korte levertijd, weinig late deliveries, hoge kwaliteit, weinig recente afkeuringen.",
            "Outputvereiste: GEEF KORTE TEKST MET PRODUCT NAAM, SUPPLIER NAAM, REDEN VAN MAX 20 WOORDEN.",
            "Regels:",
            "- Gebruik exact de supplier_name uit de opties.",
            "- Geef precies 1 recommendation per product_id hieronder.",
            "- reason moet kort, concreet en vergelijkend zijn.",
            "",
        ]

        for selection in supplier_selections:
            batched_lines.append(
                f"PRODUCT id={selection['product_id']} | naam={selection['product_name']} | code={selection['product_code']} | qty={selection['reorder_qty']}"
            )
            batched_lines.append("OPTIES:")
            for opt in selection['all_options']:
                sid = opt['supplier_id']
                if sid not in rejection_cache:
                    rejection_cache[sid] = get_last_rejection_reason(sid)
                if sid not in recent_rejection_count_cache:
                    recent_rejection_count_cache[sid] = len(get_recent_rejections(sid, days=7))

                batched_lines.append(
                    f"- naam={opt['supplier_name']} | p={opt['price_per_unit']:.2f} | lt={opt['lead_time_days']} | "
                    f"late={opt['late_deliveries_count']} | q={opt['quality_rating']}/10 | "
                    f"rej7d={recent_rejection_count_cache[sid]} | lastrej={_compact_text(rejection_cache[sid] or '-') }"
                )
            batched_lines.append("")

        batched_lines.append("Controle: lever recommendation voor ELKE product id.")

        batched_prompt = "\n".join(batched_lines)

        try:
            response = llm.invoke(batched_prompt)
            raw_recommendation = response.content
            if isinstance(raw_recommendation, list):
                raw_recommendation = " ".join(str(item) for item in raw_recommendation)
            raw_recommendation = str(raw_recommendation)
            parsed = _extract_json(raw_recommendation)
            if isinstance(parsed, dict):
                recommendations = parsed.get("recommendations", [])
                if isinstance(recommendations, list):
                    for item in recommendations:
                        if not isinstance(item, dict):
                            continue
                        pid = item.get("product_id")
                        if pid is None:
                            continue
                        recommendation_by_product[_product_key(pid)] = item
        except Exception as exc:
            print(f"WARN: batched supplier recommendation failed: {exc}")

    for selection in supplier_selections:
        selected_supplier = None
        recommendation_text = ""
        recommendation_item = recommendation_by_product.get(_product_key(selection['product_id']))

        if isinstance(recommendation_item, dict):
            supplier_name = str(recommendation_item.get("supplier_name", "")).strip().lower()
            reason = str(recommendation_item.get("reason", "")).strip()
            for opt in selection['all_options']:
                candidate = str(opt.get('supplier_name', '')).strip().lower()
                if candidate == supplier_name or (supplier_name and supplier_name in candidate) or (candidate and candidate in supplier_name):
                    selected_supplier = opt
                    break
            if selected_supplier:
                recommendation_text = (
                    f"LEVERANCIER: {selected_supplier.get('supplier_name', 'Onbekend')}\n"
                    f"REDEN: {reason or _build_supplier_reason(selected_supplier)}"
                )
            elif reason:
                selected_supplier = _choose_fallback_supplier(selection['all_options'])
                recommendation_text = (
                    f"LEVERANCIER: {selected_supplier.get('supplier_name', 'Onbekend')}\n"
                    f"REDEN: {reason}"
                )

        if not selected_supplier:
            selected_supplier = _choose_fallback_supplier(selection['all_options'])
            recommendation_text = (
                f"LEVERANCIER: {selected_supplier.get('supplier_name', 'Onbekend')}\n"
                f"REDEN: {_build_supplier_reason(selected_supplier)}"
            )

        selection['selected_supplier'] = selected_supplier
        selection['ai_recommendation'] = recommendation_text
        selection['ai_recommendation_summary'] = (
            f"{selection['product_name']}: beste match is {selected_supplier.get('supplier_name', 'Onbekend')} "
            f"voor {selection.get('reorder_qty', 0)} stuks."
        )

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
