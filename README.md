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
├── main.py           # Data generator
├── data.json         # Generated test data (created after running main.py)
├── agent/            # LangGraph agent modules
├── db/               # Database modules
└── pyproject.toml    # Project configuration
```

