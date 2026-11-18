import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from .db import get_db_connection, log_audit, init_db

DEFAULT_POLICY_V5_0 = {
    "version": "v5.0",
    "title": "Corvo Engineering Procurement Policy (PR to PO)",
    "document_ref": "CORVO-PROC-POL-04",
    "effective_date": "2026-04-01",
    "active": True,
    "parameters": {
        "anti_splitting_window_days": 14,
        "need_by_window_days": 7,
        "po_consolidation_window_hours": 24,
        "preferred_supplier_history_days": 548,
        "price_history_days": 365,
        "spot_po_limit": 200000.0,
        "emergency_po_limit": 500000.0,
        "rfq_limit": 1000000.0,
        "ranking_weights": {
            "recency": 0.25,
            "po_count": 0.20,
            "contract": 0.15,
            "on_time": 0.20,
            "quality": 0.20
        },
        "category_ranking_weights": {
            "on_time": 0.50,
            "quality": 0.50
        }
    },
    "rules": [
        {
            "id": "5.1",
            "name": "Capex Sourcing",
            "condition": {"field": "item_type", "op": "==", "value": "Capex"},
            "route": "CAPEX_SOURCING",
            "decision": "SOURCING_REQUEST",
            "suggest_count": 5,
            "supplier_selection": "none",
            "price_selection": "none",
            "require_approval": True,
            "reason_template": "Rule 5.1: Capex item requires sourcing approval"
        },
        {
            "id": "5.2",
            "name": "Contract PO",
            "condition": {"field": "contract_available", "op": "==", "value": True},
            "route": "CONTRACT_PO",
            "decision": "PO",
            "suggest_count": 0,
            "supplier_selection": "contract_supplier",
            "price_selection": "contract_rate",
            "require_approval": False,
            "reason_template": "Rule 5.2: {contract_id} valid with ceiling room"
        },
        {
            "id": "5.3",
            "name": "Emergency PO",
            "condition": {
                "and": [
                    {"field": "is_emergency", "op": "==", "value": True},
                    {"field": "value", "op": "<=", "value": 500000.0},
                    {"field": "bought_in_365d_active", "op": "==", "value": True}
                ]
            },
            "route": "EMERGENCY_PO",
            "decision": "PO",
            "suggest_count": 0,
            "supplier_selection": "1st_preferred",
            "price_selection": "reference_price",
            "require_approval": False,
            "reason_template": "Rule 5.3: Emergency under 5L with active purchase history"
        },
        {
            "id": "5.4",
            "name": "Spot PO",
            "condition": {
                "and": [
                    {"field": "value", "op": "<", "value": 200000.0},
                    {"field": "bought_in_365d_active", "op": "==", "value": True}
                ]
            },
            "route": "SPOT_PO",
            "decision": "PO",
            "suggest_count": 0,
            "supplier_selection": "1st_preferred",
            "price_selection": "reference_price",
            "require_approval": False,
            "reason_template": "Rule 5.4: Value under 2L with active purchase history"
        },
        {
            "id": "5.5",
            "name": "RFQ",
            "condition": {"field": "value", "op": "<", "value": 1000000.0},
            "route": "RFQ",
            "decision": "SOURCING_REQUEST",
            "suggest_count": 3,
            "supplier_selection": "none",
            "price_selection": "none",
            "require_approval": False,
            "reason_template": "Rule 5.5: Value under 10L requires RFQ quotes"
        },
        {
            "id": "5.6",
            "name": "RFP",
            "condition": {"field": "value", "op": ">=", "value": 1000000.0},
            "route": "RFP",
            "decision": "SOURCING_REQUEST",
            "suggest_count": 5,
            "supplier_selection": "none",
            "price_selection": "none",
            "require_approval": False,
            "reason_template": "Rule 5.6: Value 10L or more requires formal RFP"
        }
    ]
}

def evaluate_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """Evaluates a condition tree against a requirement context."""
    if not condition:
        return True

    if "and" in condition:
        return all(evaluate_condition(c, context) for c in condition["and"])

    if "or" in condition:
        return any(evaluate_condition(c, context) for c in condition["or"])

    if "not" in condition:
        return not evaluate_condition(condition["not"], context)

    field = condition.get("field")
    op = condition.get("op", "==")
    expected = condition.get("value")

    actual = context.get(field)

    if op == "==":
        return actual == expected
    elif op == "!=":
        return actual != expected
    elif op == "<":
        return actual is not None and float(actual) < float(expected)
    elif op == "<=":
        return actual is not None and float(actual) <= float(expected)
    elif op == ">":
        return actual is not None and float(actual) > float(expected)
    elif op == ">=":
        return actual is not None and float(actual) >= float(expected)
    elif op == "in":
        return actual in expected if expected else False
    elif op == "not in":
        return actual not in expected if expected else True
    elif op == "contains":
        return expected in str(actual) if actual else False

    return False

class PolicyManager:
    @staticmethod
    def ensure_default_policy():
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM policies WHERE version = ?", ("v5.0",))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
            INSERT INTO policies (version, title, document_ref, effective_date, active, policy_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                DEFAULT_POLICY_V5_0["version"],
                DEFAULT_POLICY_V5_0["title"],
                DEFAULT_POLICY_V5_0["document_ref"],
                DEFAULT_POLICY_V5_0["effective_date"],
                1,
                json.dumps(DEFAULT_POLICY_V5_0),
                datetime.now().isoformat()
            ))
            conn.commit()
        conn.close()

    @staticmethod
    def get_active_policy(as_of_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns the active policy. If as_of_date is provided, returns the policy version
        whose effective_date <= as_of_date with active=True, sorted by effective_date DESC.
        """
        PolicyManager.ensure_default_policy()
        conn = get_db_connection()
        cursor = conn.cursor()

        if as_of_date:
            cursor.execute("""
            SELECT policy_json FROM policies 
            WHERE active = 1 AND effective_date <= ?
            ORDER BY effective_date DESC, version DESC LIMIT 1
            """, (str(as_of_date),))
        else:
            cursor.execute("""
            SELECT policy_json FROM policies 
            WHERE active = 1 
            ORDER BY effective_date DESC, version DESC LIMIT 1
            """)

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row["policy_json"])
        return DEFAULT_POLICY_V5_0

    @staticmethod
    def list_policies() -> List[Dict[str, Any]]:
        PolicyManager.ensure_default_policy()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version, title, document_ref, effective_date, active, created_at FROM policies ORDER BY effective_date DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def save_and_activate_policy(policy_data: Dict[str, Any], user_id: str = "Procurement Head") -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Deactivate older policies if new one is active
        version = policy_data["version"]
        cursor.execute("UPDATE policies SET active = 0")
        
        cursor.execute("""
        INSERT OR REPLACE INTO policies (version, title, document_ref, effective_date, active, policy_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            version,
            policy_data.get("title", f"Procurement Policy {version}"),
            policy_data.get("document_ref", "CORVO-PROC-POL-AMEND"),
            policy_data.get("effective_date", datetime.now().strftime("%Y-%m-%d")),
            1,
            json.dumps(policy_data),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

        log_audit(
            user_id=user_id,
            action="ACTIVATE_POLICY",
            target_type="POLICY",
            target_id=version,
            details={"version": version, "effective_date": policy_data.get("effective_date")}
        )
        return policy_data

    @staticmethod
    def parse_amendment_text(text: str, current_policy: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[str]]:
        """
        Parses an amendment document or conversational request into a structured policy diff.
        Returns (proposed_policy, list_of_diff_descriptions)
        """
        if current_policy is None:
            current_policy = PolicyManager.get_active_policy()

        proposed = json.loads(json.dumps(current_policy))
        diffs = []

        # Version increment
        curr_ver = current_policy.get("version", "v5.0")
        ver_match = re.search(r'v(\d+)\.(\d+)', curr_ver)
        if ver_match:
            major, minor = int(ver_match.group(1)), int(ver_match.group(2))
            new_ver = f"v{major}.{minor + 1}"
        else:
            new_ver = f"{curr_ver}.1"
        
        # Explicit version in text?
        doc_ver = re.search(r'Version\s+([0-9.]+)', text, re.IGNORECASE)
        if doc_ver:
            new_ver = f"v{doc_ver.group(1)}" if not doc_ver.group(1).startswith("v") else doc_ver.group(1)

        proposed["version"] = new_ver

        # Effective date in text?
        date_match = re.search(r'Effective\s*(?:date)?[:\s]+(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
        if not date_match:
            date_match = re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})', text)
            if date_match:
                try:
                    dt = datetime.strptime(date_match.group(1), "%d %B %Y")
                    proposed["effective_date"] = dt.strftime("%Y-%m-%d")
                except:
                    proposed["effective_date"] = datetime.now().strftime("%Y-%m-%d")
            else:
                proposed["effective_date"] = datetime.now().strftime("%Y-%m-%d")
        else:
            proposed["effective_date"] = date_match.group(1)

        diffs.append(f"Policy version updated to {new_ver} (Effective: {proposed['effective_date']})")

        # 1. Spot PO limit change: e.g. "spot po limit increased to 3,00,000" or "threshold ₹3,00,000"
        spot_match = re.search(r'(?:spot(?:\s*po)?|clause\s*5\.4).*?(?:limit|threshold|below|raised to|increased to|to)\s*(?:inr|rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
        if spot_match:
            new_val = float(spot_match.group(1).replace(",", ""))
            old_val = proposed["parameters"].get("spot_po_limit", 200000.0)
            proposed["parameters"]["spot_po_limit"] = new_val
            # update Rule 5.4 in rules list
            for r in proposed["rules"]:
                if r["id"] == "5.4" or r["route"] == "SPOT_PO":
                    for cond in r["condition"].get("and", []):
                        if cond.get("field") == "value":
                            cond["value"] = new_val
                    r["reason_template"] = f"Rule 5.4: Value under ₹{int(new_val):,} with active purchase history"
            diffs.append(f"Rule 5.4 (Spot PO Limit): Changed threshold from ₹{int(old_val):,} to ₹{int(new_val):,}")

        # 2. Emergency PO limit change: e.g. "emergency limit to ₹7,50,000"
        emerg_match = re.search(r'(?:emergency(?:\s*po)?|clause\s*5\.3).*?(?:limit|threshold|below|raised to|increased to|to)\s*(?:inr|rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
        if emerg_match:
            new_val = float(emerg_match.group(1).replace(",", ""))
            old_val = proposed["parameters"].get("emergency_po_limit", 500000.0)
            proposed["parameters"]["emergency_po_limit"] = new_val
            for r in proposed["rules"]:
                if r["id"] == "5.3" or r["route"] == "EMERGENCY_PO":
                    for cond in r["condition"].get("and", []):
                        if cond.get("field") == "value":
                            cond["value"] = new_val
                    r["reason_template"] = f"Rule 5.3: Emergency under ₹{int(new_val):,} with active purchase history"
            diffs.append(f"Rule 5.3 (Emergency PO Limit): Changed threshold from ₹{int(old_val):,} to ₹{int(new_val):,}")

        # 3. RFQ / RFP threshold: e.g. "rfq limit 15,00,000" or "rfp threshold ₹15,00,000"
        rfq_match = re.search(r'(?:rfq|rfp|clause\s*5\.5|clause\s*5\.6).*?(?:limit|threshold|above|raised to|increased to|to)\s*(?:inr|rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
        if rfq_match:
            new_val = float(rfq_match.group(1).replace(",", ""))
            old_val = proposed["parameters"].get("rfq_limit", 1000000.0)
            proposed["parameters"]["rfq_limit"] = new_val
            for r in proposed["rules"]:
                if r["id"] == "5.5" or r["route"] == "RFQ":
                    r["condition"]["value"] = new_val
                    r["reason_template"] = f"Rule 5.5: Value under ₹{int(new_val):,} requires RFQ quotes"
                elif r["id"] == "5.6" or r["route"] == "RFP":
                    r["condition"]["value"] = new_val
                    r["reason_template"] = f"Rule 5.6: Value ₹{int(new_val):,} or more requires formal RFP"
            diffs.append(f"Rules 5.5 & 5.6 (RFQ/RFP Boundary): Changed threshold from ₹{int(old_val):,} to ₹{int(new_val):,}")

        # 4. Plant-specific rule addition: e.g., "For CHK1 plant, items under 50,000 go to direct spot PO"
        plant_match = re.search(r'for\s+(CHK1|PUN1)\s+plant.*?(?:under|below)\s*(?:inr|rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
        if plant_match:
            target_plant = plant_match.group(1).upper()
            plant_limit = float(plant_match.group(2).replace(",", ""))
            rule_id = f"5.4_{target_plant.lower()}"
            new_rule = {
                "id": rule_id,
                "name": f"Plant {target_plant} Direct PO",
                "condition": {
                    "and": [
                        {"field": "plant", "op": "==", "value": target_plant},
                        {"field": "value", "op": "<", "value": plant_limit}
                    ]
                },
                "route": "SPOT_PO",
                "decision": "PO",
                "suggest_count": 0,
                "supplier_selection": "1st_preferred",
                "price_selection": "reference_price",
                "require_approval": False,
                "reason_template": f"Rule {rule_id}: Plant {target_plant} direct PO under ₹{int(plant_limit):,}"
            }
            # Insert before general spot PO
            inserted = False
            for idx, r in enumerate(proposed["rules"]):
                if r["id"] == "5.4":
                    proposed["rules"].insert(idx, new_rule)
                    inserted = True
                    break
            if not inserted:
                proposed["rules"].append(new_rule)
            diffs.append(f"Added Plant-Specific Rule {rule_id}: For {target_plant}, requirements under ₹{int(plant_limit):,} route to SPOT_PO directly.")

        # 5. Anti-splitting or need-by days:
        split_match = re.search(r'anti[- ]splitting.*?(\d+)\s*days', text, re.IGNORECASE)
        if split_match:
            days = int(split_match.group(1))
            old_days = proposed["parameters"].get("anti_splitting_window_days", 14)
            proposed["parameters"]["anti_splitting_window_days"] = days
            diffs.append(f"Anti-Splitting Window: Changed from {old_days} days to {days} days")

        return proposed, diffs
