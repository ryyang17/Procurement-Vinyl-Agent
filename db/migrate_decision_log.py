"""
Migratiescript: beslissingen vanuit decision_log.json naar decision_log.db (SQLite).
Veilig om meerdere keren te draaien (duplicaten worden overgeslagen op basis van timestamp + type + supplier_id).
"""

import json
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent
JSON_PATH = DB_DIR / "decision_log.json"
SQLITE_PATH = DB_DIR / "decision_log.db"


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decision_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            type        TEXT    NOT NULL,
            supplier_id INTEGER,
            supplier_name TEXT,
            reason      TEXT,
            po_id       INTEGER,
            context     TEXT,
            actor       TEXT    NOT NULL DEFAULT 'system'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_supplier ON decision_log (supplier_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_type      ON decision_log (type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON decision_log (timestamp)")
    conn.commit()


def migrate(json_path: Path, conn: sqlite3.Connection) -> int:
    if not json_path.exists():
        print(f"[INFO] Geen JSON-bestand gevonden op {json_path}. Niets te migreren.")
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        events = json.load(f)

    inserted = 0
    skipped = 0
    for event in events:
        # Duplicaatcheck op timestamp + type + supplier_id
        exists = conn.execute(
            "SELECT 1 FROM decision_log WHERE timestamp=? AND type=? AND supplier_id IS ?",
            (event.get("timestamp"), event.get("type"), event.get("supplier_id")),
        ).fetchone()

        if exists:
            skipped += 1
            continue

        conn.execute(
            """INSERT INTO decision_log (timestamp, type, supplier_id, supplier_name, reason, po_id, context, actor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.get("timestamp"),
                event.get("type"),
                event.get("supplier_id"),
                event.get("supplier_name"),
                event.get("reason"),
                event.get("po_id"),
                json.dumps(event.get("context", {}), ensure_ascii=False),
                event.get("actor", "system"),
            ),
        )
        inserted += 1

    conn.commit()
    return inserted, skipped


if __name__ == "__main__":
    with sqlite3.connect(SQLITE_PATH) as conn:
        create_table(conn)
        inserted, skipped = migrate(JSON_PATH, conn)
        total = conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]

    print(f"[OK] Migratie voltooid.")
    print(f"     Ingevoegd : {inserted}")
    print(f"     Overgeslagen (duplicaten): {skipped}")
    print(f"     Totaal in database: {total}")

