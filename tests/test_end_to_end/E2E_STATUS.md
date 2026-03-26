# E2E Test Status

## Scope

Deze status is gebaseerd op:

- [tests/test_end_to_end/test_basis_scenarios_e2e.py](tests/test_end_to_end/test_basis_scenarios_e2e.py)
- [tests/test_end_to_end/test_edge_cases_e2e.py](tests/test_end_to_end/test_edge_cases_e2e.py)
- herhaalde runs: 11/11 tests geslaagd (meerdere keren achter elkaar)

---

## Basis E2E - Feitelijke Status

### Wat werkt goed

- End-to-end keten voor basisflow is aantoonbaar werkend:

1. Voorraadtekort detectie
2. Leveranciers vergelijken/selecteren
3. Conceptbestelling opstellen
4. Human approval verwerking
5. Order plaatsen en levering verwerken met voorraadupdate

- De basis E2E tests zijn stabiel geslaagd in meerdere opeenvolgende runs.
- De statusovergangen en kernoutput in state-data worden correct gezet (zoals reorder proposals, supplier selections, draft orders, created orders, processed deliveries).

### Wat werkt minder / beperkingen in huidige testresultaten

- Externe afhankelijkheden zijn gemockt (LLM/Spotify), dus de basis E2E-resultaten bewijzen vooral workflowlogica en niet real-life API-gedrag.
- Human approval wordt in tests via state-resume ingevoerd; dit valideert de verwerking, maar niet een volledige echte gebruikersinteractie via frontend checkpoint flow.
- Leveranciersselectie is in tests deterministischer gemaakt; productie-randomness wordt daardoor minder afgedekt in deze E2E-resultaten.

---

## Edge Cases E2E - Feitelijke Status

| Test ID | Edge Case Scenario           | Expected Result                                                                                                                                 | Actual Result                                                                                                                                                                                                     |
| ------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EC1     | Vertraagde levering          | De betrouwbaarheidsscore van de leverancier wordt aangepast en meegenomen in toekomstige leverancierskeuzes                                     | Geslaagd: bij afwijzing wegens vertraging neemt `late_deliveries` van de afgewezen leverancier toe met +1, en die geüpdatete betrouwbaarheid komt terug in volgende leveranciersopties (`late_deliveries_count`). |
| EC2     | Leverancier niet op voorraad | De agent selecteert een alternatieve leverancier of logt een melding wanneer geen alternatief beschikbaar is                                    | Geslaagd voor pad "geen alternatief": alle leveranciers tijdelijk onbeschikbaar gezet -> status `no_suppliers_found` en geen supplier selections.                                                                 |
| EC3     | Prijsfluctuatie              | De agent detecteert prijsveranderingen en genereert een waarschuwing bij significante prijsstijging                                             | Geslaagd: prijsstijging gesimuleerd, waarna `price_fluctuation_alerts` wordt gevuld met alert(s) voor het target product.                                                                                         |
| EC4     | Nieuwe release               | De agent detecteert een nieuw product en kan een bestelvoorstel genereren                                                                       | Geslaagd: nieuwe Spotify release gedetecteerd en bestelvoorstel aangemaakt (`purchase_order_proposals`) voor het nieuwe product.                                                                                  |
| EC5     | Populariteit                 | De agent moet rekening houden met de populariteit van een product bij het bepalen van de bestelhoeveelheid                                      | Geslaagd: hoeveelheid volgt populariteitsscore (hoog=10, midden=8, laag=5).                                                                                                                                       |
| EC6     | Verkoopsnelheid              | De agent moet de verkoopsnelheid van producten analyseren om te voorspellen wanneer voorraad opraakt en wanneer een nieuwe bestelling nodig is. | Geslaagd: `sales_velocity_forecasts` toont stockout/reorder-signaal (`reorder_recommended=True`), dynamisch reorder level is verhoogd, en reorder proposals worden gegenereerd.                                   |

### Wat werkt minder / beperkingen in huidige edge-case resultaten

- EC1 toont aantoonbaar effect op leverancierprestatievelden, maar de test bewijst niet in alle situaties dat een andere leverancier ook echt gekozen wordt.
- EC2 dekt het subscenario "geen alternatief beschikbaar"; het subscenario "alternatieve leverancier gekozen" is niet apart bewezen in huidige edge-case E2E.
- Edge-case tests draaien met gemockte externe bronnen en deterministische random patches; dit beperkt de representativiteit voor productievariatie.
