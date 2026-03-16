# Documentatie: Workflow Unittests

Deze documentatie beschrijft de vijf belangrijkste workflowtests voor het Procurement Vinyl Agent systeem. Elke test valideert een cruciale stap in het inkoopproces. Hieronder volgt per test een korte uitleg van het doel, de aanpak en de conclusie.

---

## Test 1: Voorraadtekort detectie (`test_1_voorraad_tekort_detectie.py`)
**Doel:**
- Controleren of het systeem producten met een voorraad onder het minimum correct detecteert.

**Wat wordt getest:**
- De node `daily_inventory_check_node` wordt aangeroepen met een initiële state.
- De test controleert of de status 'proposed' of 'ok' is.
- Bij 'proposed' wordt gecontroleerd of er herbevoorradingsvoorstellen zijn en of deze correct zijn opgebouwd.

**Conclusie:**
- Het systeem signaleert tekorten en maakt correcte voorstellen voor herbevoorrading.

---

## Test 2: Leveranciers vergelijken (`test_2_leveranciers_vergelijken.py`)
**Doel:**
- Verifiëren dat het systeem leveranciers vergelijkt en de beste optie selecteert.

**Wat wordt getest:**
- De node `find_suppliers_node` wordt aangeroepen met een state waarin een voorraadtekort is gesimuleerd.
- De LLM wordt gemockt om externe API-calls te vermijden.
- De test controleert of er leveranciersselecties zijn en of deze correct zijn opgebouwd (inclusief alle relevante velden).

**Conclusie:**
- Het systeem vergelijkt leveranciers en kiest een geschikte leverancier op basis van prijs, levertijd en kwaliteit.

---

## Test 3: Conceptbestelling opstellen (`test_3_conceptbestelling_opstellen.py`)
**Doel:**
- Controleren of het systeem concept-inkooporders correct opstelt.

**Wat wordt getest:**
- De node `create_purchase_order_node` wordt aangeroepen met een state waarin een leverancierskeuze is gemaakt.
- De test controleert of er conceptorders worden aangemaakt en of de structuur en totalen kloppen.

**Conclusie:**
- Het systeem stelt correcte concept-inkooporders op, inclusief juiste berekening van aantallen en totaalbedrag.

---

## Test 4: Human approval (`test_4_human_approval.py`)
**Doel:**
- Verifiëren dat het goedkeuringsproces door een mens correct werkt.

**Wat wordt getest:**
- De node `human_approval_node` wordt aangeroepen met een conceptorder.
- Daarna wordt het goedkeuringsproces gesimuleerd via `process_approval_node`.
- De test controleert of de status en database-updates correct zijn na goedkeuring.

**Conclusie:**
- Het systeem vraagt goedkeuring aan en verwerkt deze correct, inclusief het aanmaken van goedgekeurde orders.

---

## Test 5: Order plaatsen en voorraad bijwerken (`test_5_order_plaatsen_voorraad_bijwerken.py`)
**Doel:**
- Controleren of het plaatsen van een order de voorraad correct bijwerkt na levering.

**Wat wordt getest:**
- Er wordt een order aangemaakt en goedgekeurd.
- De leverdatum wordt gesimuleerd zodat de levering direct verwerkt kan worden.
- De test controleert of de voorraad correct is bijgewerkt en of de orderstatus 'delivered' is.

**Conclusie:**
- Het systeem verwerkt leveringen correct en werkt de voorraad en orderstatus bij zoals verwacht.

---

# Algemene conclusie
Deze vijf tests dekken het volledige inkoopproces van voorraadcontrole tot en met levering en voorraadupdate. Alle essentiële logica en integraties zijn hiermee gevalideerd. Het systeem functioneert betrouwbaar en volgens verwachting voor de belangrijkste bedrijfsprocessen.

