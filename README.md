# 🎵 Procurement Vinyl Agent

Een intelligente procurement agent voor vinyl producten, gebouwd met **LangGraph** en **SQLite**, die automatisch voorraad monitort en inkoopprocessen beheert met **Human-in-the-Loop** goedkeuringen.

## ✅ Status: **PROTOTYPE COMPLEET & WERKEND**

Alle functionele requirements (R1-R11) zijn volledig geïmplementeerd en getest!

---

## 📋 Functionele Requirements (R1-R11) - ALLE VOLTOOID

### ✅ **R1-R3: Voorraadcontrole**
- ✅ **R1**: Agent controleert **dagelijks** de voorraad
- ✅ **R2**: Genereert automatisch inkoopvoorstel wanneer voorraad onder **reorder point**
- ✅ **R3**: Bestelhoeveelheid wordt dynamisch berekend: `max_capacity - current_qty`

### ✅ **R4-R5: Leverancierskeuze**
- ✅ **R4**: Agent vergelijkt **maximaal 3 leveranciers** op prijs én levertijd
- ✅ **R5**: **Goedkoopste leverancier** met acceptabele levertijd wordt voorgesteld
  - **Scoring algoritme**: 70% prijs + 20% levertijd + 10% kwaliteitsrating

### ✅ **R6-R8: Human Approval (KRITISCH)**
- ✅ **R6**: **Elke bestelling** moet handmatig goedgekeurd worden
- ✅ **R7**: Medewerker ziet: **leverancier, bestelhoeveelheid, totale prijs**
- ✅ **R8**: Bestelling wordt **alleen geplaatst na goedkeuring**

### ✅ **R9-R10: Factuurcontrole**
- ✅ **R9**: Agent vergelijkt factuur automatisch met inkooporder
- ✅ **R10**: Bij **prijs- of aantalfouten** wordt melding gestuurd

### ✅ **R11: Leveranciershistorie**
- ✅ **R11**: Systeem slaat per leverancier op:
  - ✅ **Laatste betaalde prijs**
  - ✅ **Aantal keer te laat geleverd**
  - ✅ Kwaliteitsbeoordeling

---

## 🏗️ Architectuur (4-Layer Design)

```
┌─────────────────────────────────────────────────────────────┐
│          1. LANGGRAPH ORCHESTRATION LAYER                   │
│                  (agent/graph.py)                            │
│  Workflow: Inventory Check → Find Suppliers → Create Order  │
│                  → [Human Approval Required]                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│          2. BUSINESS LOGIC LAYER (Nodes)                    │
│                  (agent/nodes.py)                            │
│  • daily_inventory_check_node()      - R1-R3                │
│  • find_suppliers_node()             - R4-R5                │
│  • create_purchase_order_node()      - R6-R8                │
│  • human_approval_node()             - R6-R8                │
│  • verify_invoice_node()             - R9-R10               │
│  • update_supplier_history_node()    - R11                  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│          3. INTEGRATION LAYER (Database ORM)                │
│                  (agent/database.py)                         │
│  SQLite Operations voor:                                    │
│  • Suppliers & Products Management                          │
│  • Inventory Tracking                                       │
│  • Purchase Orders (met approval workflow)                  │
│  • Invoice Verification                                     │
│  • Reorder Proposals (geautomatiseerd)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│          4. SQLITE PERSISTENT DATABASE                       │
│               (data/procurement.db)                          │
│  Tables:                                                     │
│  • suppliers           - R11: last_price, late_deliveries   │
│  • supplier_products   - R4: prices per supplier            │
│  • inventory           - R1: stock levels, reorder points   │
│  • purchase_orders     - R6-R8: approval tracking           │
│  • invoices            - R9-R10: discrepancy detection      │
│  • reorder_proposals   - R2: automated proposals            │
└─────────────────────────────────────────────────────────────┘
```

**Geen JSON afhankelijkheden** - Alles persistent in SQLite!

---

## 🚀 Gebruik

### **Installatie & Start**

```bash
# 1. Install dependencies (in .venv)
pip install langchain langgraph langchain-core pydantic python-dotenv

# 2. Run the agent (initialiseert automatisch de database)
python main.py
```

### **Workflow Output Voorbeeld**

```
🎵 PROCUREMENT VINYL AGENT - SYSTEM STARTUP
======================================================================

[1/4] Checking database...
      ✓ Database ready (4 suppliers, 5 products)

[2/4] Loading workflow configuration...
      [Workflow diagram wordt getoond]

[3/4] Starting procurement workflow...

✓ Purchase order created: PO-SOU-00003 (PENDING APPROVAL)

⏸️  WORKFLOW PAUSED - AWAITING HUMAN APPROVAL
----------------------------------------------------------------------
Pending Order for Approval:
  Order Number: PO-SOU-00003
  Supplier: SoundCraft Wholesale
  Product: VINYL-005
  Quantity: 265 units
  Unit Price: €24.00
  Total Cost: €6360.00

  Status: PENDING APPROVAL
  → Manager must approve/reject this order manually
----------------------------------------------------------------------

📋 PENDING ACTIONS:
----------------------------------------------------------------------
📋 Pending Orders (1):
  • PO-SOU-00003: SoundCraft Wholesale - 265 units @ €24.0
```

---

## 📊 Database Schema

### **Suppliers** (R11: Tracking)
```sql
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    contact_person TEXT,
    email, phone, address TEXT,
    avg_lead_time_days INTEGER,
    late_deliveries_count INTEGER DEFAULT 0,  -- R11
    last_price REAL,                           -- R11
    last_order_date TIMESTAMP,
    quality_rating REAL DEFAULT 5.0
)
```

### **Inventory** (R1: Daily Check)
```sql
CREATE TABLE inventory (
    id INTEGER PRIMARY KEY,
    product_code TEXT UNIQUE NOT NULL,
    product_name TEXT,
    current_qty INTEGER,                -- R1: Checked daily
    min_threshold INTEGER DEFAULT 10,
    reorder_point INTEGER DEFAULT 20,   -- R2: Trigger
    max_capacity INTEGER DEFAULT 100,   -- R3: Calculate order qty
    last_inventory_check TIMESTAMP
)
```

### **Purchase Orders** (R6-R8: Approval)
```sql
CREATE TABLE purchase_orders (
    id INTEGER PRIMARY KEY,
    order_number TEXT UNIQUE,
    supplier_id INTEGER,
    product_code TEXT,
    quantity INTEGER,
    unit_price REAL,
    total_cost REAL,
    status TEXT DEFAULT 'pending_approval',  -- R6
    approved_at TIMESTAMP,                    -- R8
    approved_by TEXT,                         -- R8
    expected_delivery_date TIMESTAMP
)
```

### **Invoices** (R9-R10: Verification)
```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    invoice_number TEXT UNIQUE,
    order_id INTEGER,
    invoice_amount REAL,
    invoice_quantity INTEGER,
    order_amount REAL,           -- Voor vergelijking
    order_quantity INTEGER,      -- Voor vergelijking
    discrepancy_type TEXT,       -- R10: PRICE_MISMATCH / QTY_MISMATCH
    discrepancy_message TEXT,    -- R10: Alert details
    status TEXT DEFAULT 'pending_verification'
)
```

---

## 🔄 Workflow Stappen

### **Geautomatiseerde Flow** (Draait dagelijks)

#### **Stap 1: Daily Inventory Check** (R1-R3)
```python
# Controleert alle voorraad items
# Genereert proposals voor items onder reorder point
# Berekent benodigde bestelhoeveelheid

Items below reorder point:
  • VINYL-005: 35 units (reorder @ 40) → Order 265 units
  • VINYL-003: 45 units (reorder @ 50) → Order 105 units
```

#### **Stap 2: Find Suppliers** (R4-R5)
```python
# Zoekt max 3 leveranciers voor product
# Vergelijkt op: price (70%) + lead time (20%) + quality (10%)

Found 3 suppliers for VINYL-005:
  1. AudioWave Trading:  €25.00 (Score: 85.3) - 10 days
  2. SoundCraft Wholesale: €24.00 (Score: 92.1) - 6 days ✓ SELECTED
  3. VinylPro Suppliers: €26.50 (Score: 78.5) - 5 days
```

#### **Stap 3: Create Purchase Order** (R6-R8)
```python
# Creëert order met status: pending_approval
# Toont: leverancier, hoeveelheid, prijs, totale kosten

Order Created: PO-SOU-00003
  Supplier: SoundCraft Wholesale
  Quantity: 265 units @ €24.00 = €6,360.00
  Status: PENDING APPROVAL ⏸️
```

---

### **Handmatige Acties** (Human-in-the-Loop)

#### **Stap 4: Human Approval** (R6-R8)

```python
from agent.database import ProcurementDatabase

db = ProcurementDatabase()

# Bekijk pending orders
pending = db.get_pending_orders()
for order in pending:
    print(f"{order['order_number']}: {order['supplier_name']}")
    print(f"  {order['quantity']} units @ €{order['unit_price']}")
    print(f"  Total: €{order['total_cost']}")

# GOEDKEUREN
db.approve_purchase_order(order_id=1, approved_by="Jan de Manager")

# OF AFWIJZEN
db.reject_purchase_order(order_id=1, rejected_by="Jan de Manager")
```

#### **Stap 5: Invoice Verification** (R9-R10)

```python
from agent.nodes import verify_invoice_node, ProcurementState

state = ProcurementState()

# Verifieer factuur tegen order
result = verify_invoice_node(
    state=state,
    invoice_number="INV-2026-001",
    invoice_amount=6360.00,    # Verwacht: 6360.00
    invoice_quantity=265,       # Verwacht: 265
    supplier_id=4,
    order_id=1
)

# Automatische discrepancy detectie
if result.data.get('invoice_discrepancy'):
    print(f"⚠️  ALERT: {result.data['invoice_discrepancy']['message']}")
    # Output: "Invoice: €6500, Order: €6360 | Invoice Qty: 260, Order Qty: 265"
```

#### **Stap 6: Supplier History Update** (R11)

```python
from agent.database import ProcurementDatabase

db = ProcurementDatabase()

# Track late delivery
db.update_supplier_late_delivery(supplier_id=4)
# → late_deliveries_count += 1

# Update last price
db.update_supplier_last_price(supplier_id=4, price=24.00)
# → last_price = 24.00, last_order_date = NOW

# Check supplier performance
supplier = db.get_supplier_by_id(4)
print(f"Late deliveries: {supplier['late_deliveries_count']}")
print(f"Last price: €{supplier['last_price']}")
```

---

## 📁 Project Structure

```
Procurement Vinyl Agent/
├── agent/
│   ├── __init__.py
│   ├── database.py           # SQLite integration layer (R1-R11)
│   ├── nodes.py              # Business logic nodes
│   └── graph.py              # LangGraph orchestration
├── data/
│   ├── procurement.db        # SQLite database (PERSISTENT!)
│   ├── suppliers.json        # (Optional) Initial test data
│   └── inventory.json        # (Optional) Initial test data
├── main.py                   # Entry point - run workflow
├── setup_data.py             # Database initialization script
├── pyproject.toml            # Dependencies
├── .env                      # (Optional) API keys
└── README.md                 # ← You are here
```

---

## 🔑 Key Features

### ✅ **100% Persistent Data (NO JSON Dependencies)**
- Alle data in SQLite database
- JSON files alleen voor initiële setup
- Database blijft behouden tussen runs
- Geen data loss bij restart

### ✅ **Human-in-the-Loop (R6-R8)**
- Elke bestelling vereist **handmatige goedkeuring**
- Orders hebben **status tracking**
- **Goedkeurder wordt opgeslagen** (audit trail)
- Workflow pauzeert tot approval

### ✅ **Intelligente Leveranciersselectie (R4-R5)**
- Vergelijkt tot **3 leveranciers**
- **Multi-criteria scoring**:
  - 70% prijs (goedkoopste wint)
  - 20% levertijd (sneller is beter)
  - 10% kwaliteitsrating
- Gebruikt historische data (R11)

### ✅ **Automatische Factuurcontrole (R9-R10)**
- Vergelijkt factuur vs purchase order
- Detecteert:
  - Prijsverschillen (`PRICE_MISMATCH`)
  - Hoeveelheidsverschillen (`QTY_MISMATCH`)
- Automatische alerts bij discrepancies

### ✅ **Supplier Performance Tracking (R11)**
- Tracks per leverancier:
  - Aantal late leveringen
  - Laatste betaalde prijs
  - Prijsontwikkeling over tijd
  - Kwaliteitsrating

---

## 🧪 Testing & Gebruik

### **1. Complete Workflow Draaien**
```bash
python main.py
```

### **2. Database Opnieuw Initialiseren**
```bash
python setup_data.py
```

### **3. Database Status Bekijken**
```python
from agent.database import ProcurementDatabase

db = ProcurementDatabase()

# Alle leveranciers
suppliers = db.get_all_suppliers()
for s in suppliers:
    print(f"{s['name']}: {s['avg_lead_time_days']} days, Rating: {s['quality_rating']}/5")

# Voorraad status
inventory = db.get_inventory()
for item in inventory:
    print(f"{item['product_code']}: {item['current_qty']} units")

# Pending orders (wachten op goedkeuring)
pending = db.get_pending_orders()
print(f"Orders awaiting approval: {len(pending)}")

# Items met lage voorraad
low_stock = db.daily_inventory_check()
print(f"Items below reorder point: {len(low_stock['items_below_threshold'])}")
```

### **4. Order Goedkeuren**
```python
from agent.database import ProcurementDatabase

db = ProcurementDatabase()

# Get first pending order
pending = db.get_pending_orders()
if pending:
    order = pending[0]
    
    # Approve it
    success = db.approve_purchase_order(
        order_id=order['id'],
        approved_by="Manager Naam"
    )
    
    if success:
        print(f"✓ Order {order['order_number']} approved!")
```

---

## 🎯 Next Steps (Future Enhancements)

### **Phase 2: Memory System**
- [ ] Time-series tracking van prijzen per leverancier
- [ ] Seasonal pattern detectie voor voorraad
- [ ] Predictive reordering (ML model)
- [ ] Price trend analysis & alerts

### **Phase 3: Edge Cases**
- [ ] Supplier out of stock handling
- [ ] Multiple concurrent proposals
- [ ] Budget constraints & optimization
- [ ] Urgent orders (priority queue)
- [ ] Partial deliveries tracking

### **Phase 4: LLM Integration**
- [ ] Natural language queries: "Wie is onze beste leverancier?"
- [ ] Automated email generation naar leveranciers
- [ ] Smart negotiation suggestions
- [ ] Anomaly detection in orders

### **Phase 5: Reporting & Analytics**
- [ ] Cost savings dashboard
- [ ] Supplier performance reports
- [ ] Inventory turnover metrics
- [ ] Budget vs actual spending
- [ ] Export naar Excel/PDF

---

## 📝 Requirements Checklist - COMPLEET

- [x] **R1**: Dagelijkse voorraadcontrole
- [x] **R2**: Inkoopvoorstel bij voorraad < minimum
- [x] **R3**: Dynamische bestelhoeveelheid
- [x] **R4**: Vergelijk maximaal 3 leveranciers
- [x] **R5**: Goedkoopste met acceptabele levertijd
- [x] **R6**: Handmatige goedkeuring vereist
- [x] **R7**: Toon leverancier, hoeveelheid, prijs
- [x] **R8**: Bestelling alleen na goedkeuring
- [x] **R9**: Vergelijk factuur met PO
- [x] **R10**: Melding bij prijs/aantal fouten
- [x] **R11**: Track laatste prijs & late leveringen

**Status: ✅ 11/11 Requirements Geïmplementeerd**

---

## 🛠️ Technologies

| Technology | Versie | Gebruik |
|-----------|--------|---------|
| **Python** | 3.11+ | Runtime |
| **LangGraph** | Latest | Workflow orchestration |
| **SQLite** | 3 | Persistent database |
| **Pydantic** | 2.x | Data validation |
| **LangChain** | Latest | (Optional) LLM integration |

---

## 📄 License

MIT License

---

## 👨‍💻 Ontwikkelaar Notities

### **Database Locatie**
```
data/procurement.db
```

### **Belangrijke Functies**

```python
# Daily inventory check (automatisch)
result = db.daily_inventory_check()

# Zoek beste leverancier
suppliers = db.find_suppliers_for_product("VINYL-001", limit=3)

# Maak order (pending approval)
order = db.create_purchase_order(
    supplier_id=1,
    product_code="VINYL-001",
    quantity=100,
    unit_price=12.50
)

# Goedkeuren
db.approve_purchase_order(order_id=1, approved_by="Manager")

# Verifieer factuur
invoice = db.create_invoice(
    invoice_number="INV-001",
    order_id=1,
    supplier_id=1,
    invoice_amount=1250.00,
    invoice_quantity=100
)
```

---

## 🎉 Conclusie

**Dit is een volledig werkend prototype** dat alle 11 functionele requirements implementeert met:

✅ Persistent SQLite database (geen JSON dependencies)  
✅ Human-in-the-Loop approval workflow  
✅ Intelligente leveranciersselectie  
✅ Automatische factuurcontrole  
✅ Supplier performance tracking  

**Ready voor productie na uitbreiding met memory systeem en edge case handling!**

---

**Voor vragen of support:** Open een issue in de repository.

