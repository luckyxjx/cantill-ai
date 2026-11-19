import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from .config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Policies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS policies (
        version TEXT PRIMARY KEY,
        title TEXT,
        document_ref TEXT,
        effective_date TEXT,
        active BOOLEAN,
        policy_json TEXT,
        created_at TEXT
    );
    """)
    
    # 2. Audit logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        user_id TEXT,
        action TEXT,
        target_type TEXT,
        target_id TEXT,
        details TEXT
    );
    """)
    
    # 3. Buyer actions table (approvals / overrides)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buyer_actions (
        group_id TEXT PRIMARY KEY,
        batch_id TEXT,
        status TEXT, -- PENDING, APPROVED, OVERRIDDEN
        override_reason TEXT,
        action_by TEXT,
        action_at TEXT,
        final_po_id TEXT,
        final_supplier_id TEXT,
        final_price REAL,
        details TEXT
    );
    """)
    
    # 4. Chat PR intake sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT,
        updated_at TEXT,
        state_json TEXT,
        messages_json TEXT
    );
    """)
    
    # 5. Additional / Extracted contracts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contracts_extracted (
        contract_id TEXT PRIMARY KEY,
        supplier_id TEXT,
        supplier_name TEXT,
        start_date TEXT,
        end_date TEXT,
        value_cap REAL,
        consumed_value REAL,
        lines_json TEXT,
        source TEXT,
        created_at TEXT
    );
    """)

    # 6. Master data tables (seeded from seed_data.py — no CSV files needed at runtime)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_master (
        item_code TEXT PRIMARY KEY,
        description TEXT,
        uom TEXT,
        category TEXT,
        item_type TEXT,
        standard_price REAL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plants (
        plant TEXT PRIMARY KEY,
        name TEXT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS supplier_master (
        supplier_id TEXT PRIMARY KEY,
        name TEXT,
        city TEXT,
        categories TEXT,
        status TEXT,
        on_time_pct REAL,
        quality_rating REAL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS po_history (
        po_number TEXT,
        po_date TEXT,
        supplier_id TEXT,
        item_code TEXT,
        quantity REAL,
        uom TEXT,
        unit_price REAL,
        plant TEXT,
        delivered_on_time INTEGER
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contract_lines (
        contract_id TEXT,
        item_code TEXT,
        description TEXT,
        uom TEXT,
        rate REAL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contract_register (
        contract_id TEXT PRIMARY KEY,
        supplier_id TEXT,
        supplier_name TEXT,
        start_date TEXT,
        end_date TEXT,
        value_cap REAL,
        consumed_value REAL
    );
    """)

    # Seed master data if tables are empty
    if cursor.execute("SELECT COUNT(*) FROM item_master").fetchone()[0] == 0:
        from .seed_data import ITEM_MASTER, PLANTS, SUPPLIER_MASTER, PO_HISTORY, CONTRACT_LINES, CONTRACT_REGISTER
        cursor.executemany(
            "INSERT OR IGNORE INTO item_master VALUES (?,?,?,?,?,?)",
            [(r['item_code'], r['description'], r['uom'], r['category'], r['item_type'], float(r['standard_price'] or 0)) for r in ITEM_MASTER]
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO plants VALUES (?,?)",
            [(r['plant'], r['name']) for r in PLANTS]
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO supplier_master VALUES (?,?,?,?,?,?,?)",
            [(r['supplier_id'], r['name'], r['city'], r['categories'], r['status'],
              float(r['on_time_pct'] or 0), float(r['quality_rating'] or 0)) for r in SUPPLIER_MASTER]
        )
        cursor.executemany(
            "INSERT INTO po_history VALUES (?,?,?,?,?,?,?,?,?)",
            [(r['po_number'], r['po_date'], r['supplier_id'], r['item_code'],
              float(r['quantity'] or 0), r['uom'], float(r['unit_price'] or 0),
              r['plant'], 1 if str(r['delivered_on_time']).strip().upper() in ('1','TRUE','YES') else 0) for r in PO_HISTORY]
        )
        cursor.executemany(
            "INSERT INTO contract_lines VALUES (?,?,?,?,?)",
            [(r['contract_id'], r['item_code'], r['description'], r['uom'], float(r['rate'] or 0)) for r in CONTRACT_LINES]
        )
        cursor.executemany(
            "INSERT OR IGNORE INTO contract_register VALUES (?,?,?,?,?,?,?)",
            [(r['contract_id'], r['supplier_id'], r['supplier_name'], r['start_date'], r['end_date'],
              float(r['value_cap'] or 0), float(r['consumed_value'] or 0)) for r in CONTRACT_REGISTER]
        )
        print(f"[DB] Seeded master data: {len(ITEM_MASTER)} items, {len(SUPPLIER_MASTER)} suppliers, {len(PO_HISTORY)} PO records")

    conn.commit()
    conn.close()

def log_audit(user_id: str, action: str, target_type: str, target_id: str, details: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO audit_logs (timestamp, user_id, action, target_type, target_id, details)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), user_id, action, target_type, target_id, json.dumps(details)))
    conn.commit()
    conn.close()

def get_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['details'] = json.loads(d['details']) if d['details'] else {}
        result.append(d)
    return result

