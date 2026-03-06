# Procurement Vinyl Agent

Data generator voor het Procurement Vinyl Agent project.

## Snelle Start

1. **Data genereren:**
   ```bash
   python main.py
   ```
   
   Dit genereert een `data.json` bestand met test data voor alle 7 tabellen.

## Database Schema

- **PRODUCT** (100 records) - Vinyl producten met prijzen
- **SUPPLIER** (100 records) - Leveranciers informatie
- **INVENTORY** (100 records) - Voorraadbeheer
- **PURCHASE_ORDER** (100 records) - Inkooporders
- **PURCHASE_ORDER_ITEM** (300+ records) - Order items
- **PRICE_HISTORY** (150+ records) - Prijsgeschiedenis
- **SUPPLIER_PERFORMANCE** (100 records) - Leverancier beoordelingen

## Output

`data.json` bevat alle test data in volgende structuur:

```json
{
  "PRODUCT": [...],
  "SUPPLIER": [...],
  "INVENTORY": [...],
  "PURCHASE_ORDER": [...],
  "PURCHASE_ORDER_ITEM": [...],
  "PRICE_HISTORY": [...],
  "SUPPLIER_PERFORMANCE": [...]
}
```

## Dependencies

- Python 3.11+
- faker (voor realistische test data)

Installeer met:
```bash
pip install faker
```

## File Structuur

```
Procurement Vinyl Agent/
├── main.py                    # Manager interface entrypoint
├── agent/                     # LangGraph agent modules
│   ├── agent.py              # Workflow definition + checkpointing
│   ├── procurement_data.py   # Database access layer
│   └── utils/
│       ├── memory.py         # Decision log (LONG-TERM memory)
│       ├── state.py          # Workflow state model
│       └── nodes/            # Workflow nodes
├── db/                        # Data storage
│   ├── checkpoints.sqlite    # SHORT-TERM: Workflow state
│   ├── decision_log.json     # LONG-TERM: Business decisions
│   ├── inventory.json        # Business data
│   └── *.json                # Other business data
├── MEMORY_ARCHITECTURE.md     # ⭐ Waarom 2 memory systemen?
└── pyproject.toml            # Project configuration
```

## Memory Architecture

Dit systeem gebruikt **2 verschillende memory systemen** met verschillende doelen:

1. **Checkpointing** (`db/checkpoints.sqlite`) - SHORT-TERM workflow state
   - Voor workflow pause/resume bij human-in-the-loop
   - Managed door LangGraph framework
   - Kan periodiek gewist worden

2. **Decision Log** (`db/decision_log.json`) - LONG-TERM business memory
   - Voor manager beslissingen en supplier performance
   - Managed door procurement agent
   - Permanent, mag nooit gewist worden

**Zie [MEMORY_ARCHITECTURE.md](MEMORY_ARCHITECTURE.md) voor volledige uitleg waarom beide nodig zijn.**

