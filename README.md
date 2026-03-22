# Procurement Vinyl Agent

Een intelligente AI-agent voor vinylprocurement met MCP (Model Context Protocol) integratie voor realtime Discogs API toegang.

## 🌟 Nieuwe Functies

### 📡 MCP Discogs Integration

- **Realtime data**: Echte vinylreleases via Discogs API
- **Gestandaardiseerd protocol**: Model Context Protocol voor robuuste API integratie
- **Automatische fallback**: Graceful degradation naar simulatie modus
- **Artist search**: Zoek specifieke artiesten voor procurement analyse

Zie [MCP_README.md](MCP_README.md) voor gedetailleerde MCP documentatie.

## Snelle Start

1. **Basis installatie:**

   ```bash
   pip install -r requirements.txt
   ```

2. **MCP functionaliteit (optioneel):**

   ```bash
   pip install mcp httpx
   ```

3. **Start de agent:**
   ```bash
   python main.py
   ```

### Menu Opties

- **1. Procurement Workflow**: Normale inventory en order workflow
- **2. MCP New Release Detection**: Realtime Discogs data (als MCP beschikbaar)
- **3. Simulation Mode**: Mock data voor testing
- **4. Pending Orders**: Bekijk openstaande bestellingen
- **5. Decision History**: Recente procurement beslissingen

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

## Checkpoint API voor Frontend

Voor een eenvoudige prototype setup gebruikt de Next.js frontend direct de LangGraph server (standaard `http://127.0.0.1:2024`) om workflow-checkpoints op te halen en te hervatten.

De benodigde backend endpoints zijn:

- `GET /checkpoints/pending`
  - Geeft alle openstaande threads terug die wachten op human approval/path selectie.
- `GET /checkpoints/{thread_id}`
  - Geeft de laatste state van een specifieke thread terug.
- `POST /checkpoints/{thread_id}/decision`
  - Verwerkt een beslissing en hervat de workflow in dezelfde thread.

Voorbeeld payload voor beslissing:

```json
{
  "approved_indices": [0, 1],
  "rejection_reasons_by_index": { "2": "Budget te hoog" },
  "approved_by": "manager",
  "decision": "approved"
}
```

In de Next.js frontend zijn proxy routes toegevoegd zodat je vanuit de UI direct kunt werken met:

- `GET /api/checkpoints/pending`
- `GET /api/checkpoints/{threadId}`
- `POST /api/checkpoints/{threadId}/decision`

Stel eventueel backend URL in met:

- `PROCUREMENT_BACKEND_URL=http://127.0.0.1:2024`
