# Memory Systeem Testresultaten

**Let op:** De onderstaande 4 testen zijn alleen unit- en integratietests van je eigen code en zijn niet afhankelijk van LangGraph. Met LangGraph kun je end-to-end workflowtesten uitvoeren; deze worden in een andere map weergegeven.

Hieronder vind je een samenvatting van de long term en short term memory testresultaten. Per test staat wat er wordt getest en hoe het geheugen jouw agent slimmer maakt.

---

## Test 1: Voorraadtekort (Beslissing Loggen)
**Wat wordt getest:**
- Herkent wanneer een product bijna op is
- Kiest de beste leverancier
- Slaat goedkeuringsbeslissing op in het geheugen

**Hoe helpt geheugen?**
- Agent weet welke producten snel besteld moeten worden
- Kan altijd terugvinden waarom en bij wie besteld is

---

## Test 2: Te Late Levering (Prestaties Bijwerken)
**Wat wordt getest:**
- Logt afkeuring bij vertraging
- Past prestaties van leverancier aan (betrouwbaarheid omlaag, aantal te late leveringen omhoog)

**Hoe helpt geheugen?**
- Agent leert welke leveranciers vaak te laat zijn
- Kan onbetrouwbare leveranciers vermijden in de toekomst

---

## Test 3: Leveranciersgeschiedenis (Opvragen)
**Wat wordt getest:**
- Haalt alle beslissingen voor een leverancier op
- Telt goedkeuringen en afkeuringen

**Hoe helpt geheugen?**
- Agent kan snel zien hoe vaak een leverancier is goed- of afgekeurd
- Maakt betere keuzes op basis van eerdere ervaringen

---

## Test 4: Checkpointer (Short-term Memory & Workflow Resume)
**Wat wordt getest:**
- Slaat de actuele workflow state op in een SQLite database (`checkpoints.sqlite`)
- Pauzeert de workflow bij human-in-the-loop (goedkeuring nodig)
- Hervat de workflow later met dezelfde `thread_id` en verwerkt de menselijke beslissing

**Hoe helpt short-term memory?**
- Agent kan workflows hervatten na onderbreking of bij menselijke input
- Voorkomt dat werk verloren gaat bij een crash of stop
- Zorgt dat de agent altijd weet waar hij gebleven is, zelfs na een restart

**Voorbeeldscenario:**
1. Start een workflow met een unieke `thread_id`.
2. Workflow pauzeert en wacht op menselijke goedkeuring (bijvoorbeeld bij een grote bestelling).
3. De state wordt opgeslagen in `checkpoints.sqlite`.
4. Na goedkeuring door een mens wordt de workflow hervat met dezelfde `thread_id`.
5. De agent verwerkt de beslissing en rondt de workflow af.
6. In de database kun je terugvinden dat de state tussentijds is opgeslagen en hervat.

---

## Waarom maakt geheugen je agent slimmer?
- Onthoudt alle beslissingen en prestaties
- Leert van fouten 
- Kan uitleggen waarom een keuze is gemaakt
- Zorgt voor snellere en betere beslissingen
