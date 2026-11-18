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

