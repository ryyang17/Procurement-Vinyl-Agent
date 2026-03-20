# Memory Architecture - Waarom 2 Memory Systemen?

**Datum:** 2026-03-06  
**Status:** Architecturele beslissing - BEHOUDEN zoals het is

---

## TL;DR

✅ **Beide memory-systemen zijn nodig en hebben VERSCHILLENDE doelen:**

1. **Checkpointing (checkpoints.sqlite)** = SHORT-TERM workflow state  
2. **Decision Log (decision_log.json)** = LONG-TERM business memory; deze log wordt nu in de sqlite database opgeslagen. 

Deze twee zijn **NIET redundant** en moeten gescheiden blijven.

---

## Overzicht

| Aspect | Checkpointing | Decision Log |
|--------|---------------|--------------|
| **Type** | Technical/Infrastructure | Business/Domain |
| **Eigenaar** | LangGraph framework | Procurement agent logica |
| **Scope** | Per workflow-run (thread_id) | Alle runs, cross-sessie |
| **Levensduur** | Tijdelijk (tot workflow compleet) | Permanent (voor altijd) |
| **Doel** | Workflow hervatten bij crash/pause | Supplier analyse & learning |
| **Opslag** | SQLite binary (checkpoints.sqlite) | JSON human-readable (decision_log.json) |
| **Gebruikt door** | LangGraph engine intern | Manager interface, supplier nodes |
| **Kan gewist worden?** | Ja, periodiek cleanup mogelijk | Nee, dit IS de business data |

---

## Use Cases per Memory Type

### Checkpointing (SHORT-TERM)

**Wat wordt opgeslagen:**
- Huidige stap in workflow (`daily_inventory_check`, `awaiting_human_input`, etc.)
- Tijdelijke state-data (`draft_orders`, `supplier_selections`)
- Thread ID voor sessie-tracking
- Graph execution state (voor LangGraph engine)

**Wanneer gebruikt:**
1. Manager keurt orders goed → workflow pauzeert → manager komt terug → workflow hervat
2. System crash tijdens workflow → bij restart kan workflow verder waar het was
3. Debugging: kunnen we zien waar workflow vast zit?

**Voorbeeld:**
```python
# main.py
thread_id = str(uuid.uuid4())[:8].upper()  # Uniek per workflow-run
state = ProcurementState(thread_id=thread_id)
result = workflow.invoke(state, config={"configurable": {"thread_id": thread_id}})
# LangGraph gebruikt checkpointer om state op te slaan tussen nodes
```

**Lifecycle:**
- Created: bij start workflow
- Updated: na elke node execution
- Deleted: kan periodiek gewist (bijv. na 30 dagen inactiviteit)

---

### Decision Log (LONG-TERM)

**Wat wordt opgeslagen:**
- Alle approval/rejection beslissingen van managers
- Redenen voor afwijzing (bijv. "leverancier te duur", "kwaliteit slecht")
- Supplier performance tracking data
- Historische context voor toekomstige beslissingen

**Wanneer gebruikt:**
1. Supplier performance berekenen: hoeveel keer werd deze leverancier afgewezen?
2. Manager analytics: waarom wijzen we leveranciers af?
3. Agent learning: welke suppliers vermijden we in de toekomst?
4. Compliance & audit trail: wie heeft wat wanneer goedgekeurd?

**Voorbeeld:**
```python
# approval_nodes.py - na manager-beslissing
log_decision(
    decision_type='supplier_rejected',
    supplier_id=draft['supplier_id'],
    supplier_name=draft['supplier_name'],
    reason="Te duur en slechte levertijd",  # Manager input
    actor="user"
)

# Later in supplier_nodes.py - agent gebruikt dit geheugen
summary = get_supplier_summary(supplier_id)
if summary['rejection_count'] > 5:
    # Skip deze leverancier automatisch
```

**Lifecycle:**
- Created: elke keer als manager een beslissing maakt
- Updated: nooit (append-only log)
- Deleted: nooit (dit is permanent business data)

---

## Waarom NIET samenvoegen?

### Reden 1: Verschillende Eigenaars
- **Checkpointing** wordt beheerd door LangGraph framework (externe library)
- **Decision Log** is onze eigen business logica

Als we decision log in checkpointing stoppen, verliezen we controle en kunnen we niet meer:
- Querien over alle leverancier-beslissingen (cross-workflow)
- Oude checkpoints opruimen zonder beslissingen te verliezen
- Human-readable logs inzien (SQLite is binair, JSON is leesbaar)

### Reden 2: Verschillende Levenscyclus
- **Checkpointing** is per workflow-run → kan na afronding gewist
- **Decision Log** is voor altijd → mag NOOIT gewist

Als we deze mengen, kunnen we geen cleanup doen zonder data-verlies.

### Reden 3: Verschillende Query Patterns
- **Checkpointing** query: "Geef me state van thread_id X op tijdstip Y"
- **Decision Log** query: "Hoeveel keer werd supplier 5 afgewezen in laatste 90 dagen?"

Deze query's vereisen verschillende data-structuren en indexen.

### Reden 4: Compliance & Audit
- **Decision Log** = audit trail voor management beslissingen
- **Checkpointing** = technical infrastructure

In productie wil je audit trails **gescheiden van technical state**, bijvoorbeeld:
- Audit logs kunnen naar compliance-systeem geëxporteerd worden
- Technical checkpoints blijven in development/staging

---

## Alternative Overwogen (en Afgewezen)

### ❌ Optie A: Alles in Checkpointing
**Probleem:** 
- We verliezen controle over data-lifecycle
- Cleanup wordt onmogelijk zonder data-verlies
- Cross-workflow queries worden complex/traag

### ❌ Optie B: Alles in Decision Log
**Probleem:**
- LangGraph vereist een checkpointer voor human-in-the-loop
- We moeten dan zelf workflow-resumption logica bouwen
- Geen support voor native LangGraph features (time-travel debugging, etc.)

### ❌ Optie C: Één gedeelde database met 2 tabellen
**Mogelijke optie, maar:**
- Mixing concerns: technical state + business data
- Nog steeds 2 query-patterns, maar nu in 1 database
- Maakt migratie/export/backup complexer
- Geen duidelijke voordelen boven huidige scheiding

---

## Beslissing: BEHOUDEN zoals het is

**Reden:**
- Beide systemen hebben duidelijk **verschillende verantwoordelijkheden** (Separation of Concerns)
- De overhead is minimaal (2 bestanden, beide efficient)
- Het biedt maximale **flexibiliteit** voor toekomstige use-cases

**Trade-offs geaccepteerd:**
- Wel: 2 aparte bestanden te onderhouden
- Maar: elk bestand heeft één duidelijk doel en één eigenaar

---

## Best Practices voor Ontwikkelaars

### Gebruik Checkpointing voor:
✅ Workflow state (welke stap zijn we?)
✅ Tijdelijke data binnen een workflow-run
✅ Human-in-the-loop pause/resume
✅ Debugging workflow execution

### Gebruik Decision Log voor:
✅ Manager goedkeuringen/afwijzingen
✅ Supplier performance tracking
✅ Historical analytics
✅ Audit trails

### NOOIT:
❌ Business beslissingen alleen in checkpointing (gaat verloren bij cleanup)
❌ Workflow state alleen in decision log (geen LangGraph support)

---

## Code Locaties

```
agent/
├── agent.py                    # Checkpointing setup (get_checkpointer)
├── utils/
│   ├── memory.py              # Decision Log API (log_decision, get_supplier_summary)
│   └── nodes/
│       └── approval_nodes.py  # Gebruikt BEIDE: state voor workflow, log_decision voor history
db/
├── checkpoints.sqlite         # LangGraph checkpointing (kan gewist)
└── decision_log.json          # Business memory (permanent)
```

---

## Toekomstige Uitbreidingen

Beide systemen kunnen onafhankelijk groeien:

**Checkpointing:**
- Kan migreren naar Redis voor distributed workflows
- Kan gebruik maken van LangGraph Cloud features
- Blijft technical infrastructure

**Decision Log:**
- Kan uitbreiden naar PostgreSQL/analytics database
- Kan gekoppeld worden aan BI tools (Metabase, Tableau)
- Kan dienen als input voor ML models (supplier recommendation)
- Blijft business data

Door ze gescheiden te houden, blijven deze migraties **onafhankelijk en simpel**.

---

## Conclusie

**Vraag:** Waarom twee memory-systemen?

**Antwoord:** Omdat ze fundamenteel verschillende dingen doen:
1. **Checkpointing** = workflow engine state (technical)
2. **Decision Log** = business beslissingen (domain)

Dit is **geen duplicatie**, maar **separation of concerns**.

Het samenvoegen zou leiden tot:
- Verlies van controle over data-lifecycle
- Menging van technical en business concerns
- Complexere queries en maintenance
- Geen duidelijke voordelen

**Besluit: BEHOUDEN als-is.**

---

**Laatste update:** 2026-03-06  
**Maintainer:** Procurement Agent Team  
**Review datum:** 2026-09-01 (6 maanden)

