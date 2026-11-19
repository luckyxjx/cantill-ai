import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import glob
import os

from .config import (
    PLANTS_CSV, ITEM_MASTER_CSV, SUPPLIER_MASTER_CSV, PO_HISTORY_CSV,
    CONTRACT_REGISTER_CSV, CONTRACT_LINES_CSV, CONTRACTS_PDF_DIR
)
from .item_matcher import ItemMatcher
from .pdf_parser import parse_contract_pdf
from .policy_engine import PolicyManager, evaluate_condition
from .schemas import PRLineInput, PRDecisionOutput, PreferredSupplierRow

class DecisionEngine:
    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        self.item_matcher = ItemMatcher(ITEM_MASTER_CSV)
        self.load_master_data()
        self.load_contracts()
        self.policy = policy or PolicyManager.get_active_policy()

    def load_master_data(self):
        self.plants_df = pd.read_csv(PLANTS_CSV)
        self.valid_plants = set(self.plants_df['plant'].str.strip())

        self.items_df = pd.read_csv(ITEM_MASTER_CSV)
        self.suppliers_df = pd.read_csv(SUPPLIER_MASTER_CSV)
        self.po_history_df = pd.read_csv(PO_HISTORY_CSV)
        self.po_history_df['po_dt'] = pd.to_datetime(self.po_history_df['po_date'])

        self.active_suppliers = set(
            self.suppliers_df[self.suppliers_df['status'] == 'Active']['supplier_id']
        )
        self.supplier_map = {row['supplier_id']: row for _, row in self.suppliers_df.iterrows()}
        self.item_map = {row['item_code']: row for _, row in self.items_df.iterrows()}

    def load_contracts(self):
        self.contract_register_df = pd.read_csv(CONTRACT_REGISTER_CSV)
        self.contract_lines_df = pd.read_csv(CONTRACT_LINES_CSV)

        # Parse all PDF contracts in CONTRACTS_PDF_DIR
        pdf_contracts = []
        pdf_lines = []
        if os.path.exists(CONTRACTS_PDF_DIR):
            for pdf_file in sorted(glob.glob(os.path.join(CONTRACTS_PDF_DIR, "*.pdf"))):
                c_id = os.path.splitext(os.path.basename(pdf_file))[0]
                if c_id not in self.contract_register_df['contract_id'].values:
                    parsed = parse_contract_pdf(pdf_file)
                    pdf_contracts.append({
                        'contract_id': parsed['contract_id'],
                        'supplier_id': parsed['supplier_id'],
                        'supplier_name': parsed['supplier_name'],
                        'start_date': parsed['start_date'],
                        'end_date': parsed['end_date'],
                        'value_cap': parsed['value_cap'],
                        'consumed_value': 0.0
                    })
                    for l in parsed['lines']:
                        pdf_lines.append(l)

        if pdf_contracts:
            self.contract_register_df = pd.concat(
                [self.contract_register_df, pd.DataFrame(pdf_contracts)],
                ignore_index=True
            )
        if pdf_lines:
            self.contract_lines_df = pd.concat(
                [self.contract_lines_df, pd.DataFrame(pdf_lines)],
                ignore_index=True
            )

        # Also load dynamically ingested contracts from SQLite contracts_extracted
        try:
            import json
            from .db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT contract_id, supplier_id, supplier_name, start_date, end_date, value_cap, consumed_value, lines_json FROM contracts_extracted")
            db_rows = cursor.fetchall()
            conn.close()
            db_contracts = []
            db_lines = []
            for r in db_rows:
                if r['contract_id'] not in self.contract_register_df['contract_id'].values:
                    db_contracts.append({
                        'contract_id': r['contract_id'],
                        'supplier_id': r['supplier_id'],
                        'supplier_name': r['supplier_name'],
                        'start_date': r['start_date'],
                        'end_date': r['end_date'],
                        'value_cap': float(r['value_cap']),
                        'consumed_value': float(r['consumed_value'])
                    })
                    for l in json.loads(r['lines_json']):
                        db_lines.append(l)
            if db_contracts:
                self.contract_register_df = pd.concat([self.contract_register_df, pd.DataFrame(db_contracts)], ignore_index=True)
            if db_lines:
                self.contract_lines_df = pd.concat([self.contract_lines_df, pd.DataFrame(db_lines)], ignore_index=True)
        except Exception:
            pass

        self.contract_consumed = {
            row['contract_id']: float(row['consumed_value'])
            for _, row in self.contract_register_df.iterrows()
        }

    def reset_contract_consumed(self):
        self.contract_consumed = {
            row['contract_id']: float(row['consumed_value'])
            for _, row in self.contract_register_df.iterrows()
        }

    def get_preferred_suppliers(self, item_code: str, as_of_date: datetime) -> List[Dict[str, Any]]:
        """
        Builds the preferred supplier list as of as_of_date for item_code (Policy Section 6).
        """
        if item_code == "NEW":
            return []

        weights = self.policy.get("parameters", {}).get("ranking_weights", {
            "recency": 0.25, "po_count": 0.20, "contract": 0.15, "on_time": 0.20, "quality": 0.20
        })

        req_dt = pd.to_datetime(as_of_date)
        history_window = self.policy.get("parameters", {}).get("preferred_supplier_history_days", 548)

        # 1. POs for item in last 548 days
        po_sub = self.po_history_df[
            (self.po_history_df['item_code'] == item_code) &
            (self.po_history_df['po_dt'] <= req_dt) &
            (self.po_history_df['po_dt'] >= req_dt - timedelta(days=history_window))
        ]

        # 2. Contracts covering item starting on or before req_dt
        c_item = self.contract_lines_df[self.contract_lines_df['item_code'] == item_code].merge(
            self.contract_register_df, on='contract_id'
        )
        c_item['start_dt'] = pd.to_datetime(c_item['start_date'])
        c_valid = c_item[c_item['start_dt'] <= req_dt]

        # Eligible Active suppliers
        eligible = set()
        for s in po_sub['supplier_id'].unique():
            if s in self.active_suppliers:
                eligible.add(s)
        for s in c_valid['supplier_id'].unique():
            if s in self.active_suppliers:
                eligible.add(s)

        scored = []
        for s in eligible:
            s_pos = po_sub[po_sub['supplier_id'] == s]
            po_count = len(s_pos)
            rec = 0.0
            ref_price = None

            if po_count > 0:
                last_po = s_pos.sort_values(by=['po_dt', 'po_number'], ascending=[False, False]).iloc[0]
                days_ago = (req_dt - last_po['po_dt']).days
                if days_ago <= 90:
                    rec = 1.0
                elif days_ago <= 365:
                    rec = 0.5
                else:
                    rec = 0.0
                ref_price = float(last_po['unit_price'])

            has_contract = 1.0 if s in c_valid['supplier_id'].values else 0.0
            if ref_price is None and has_contract:
                c_s = c_valid[c_valid['supplier_id'] == s].sort_values(by='start_dt', ascending=False)
                ref_price = float(c_s.iloc[0]['rate'])

            supp_info = self.supplier_map.get(s)
            ot = (float(supp_info['on_time_pct']) / 100.0) if supp_info is not None else 0.0
            q = (float(supp_info['quality_rating']) / 5.0) if supp_info is not None else 0.0
            po_norm = min(po_count / 5.0, 1.0)

            score = (
                weights.get("recency", 0.25) * rec +
                weights.get("po_count", 0.20) * po_norm +
                weights.get("contract", 0.15) * has_contract +
                weights.get("on_time", 0.20) * ot +
                weights.get("quality", 0.20) * q
            )

            scored.append({
                'supplier_id': s,
                'supplier_name': supp_info['name'] if supp_info is not None else s,
                'score': round(score, 4),
                'reference_price': ref_price,
                'recency': rec,
                'po_count': po_count,
                'has_contract': bool(has_contract),
                'on_time_pct': int(supp_info['on_time_pct']) if supp_info is not None else 0,
                'quality_rating': float(supp_info['quality_rating']) if supp_info is not None else 0.0
            })

        scored.sort(key=lambda x: (-x['score'], x['supplier_id']))
        for i, item in enumerate(scored):
            item['rank'] = i + 1

        return scored

    def get_sourcing_suggestions(self, item_code: str, as_of_date: datetime, count_needed: int) -> List[str]:
        """
        Suggests suppliers for RFQ/RFP/Capex (Clause 6.4).
        Takes preferred list in order, tops up from item category sorted by delivery & quality.
        """
        if item_code == "NEW":
            return []

        pref = self.get_preferred_suppliers(item_code, as_of_date)
        result = [p['supplier_id'] for p in pref]
        if len(result) >= count_needed:
            return result[:count_needed]

        # Category top-up
        cat = self.item_map[item_code]['category']
        cat_weights = self.policy.get("parameters", {}).get("category_ranking_weights", {"on_time": 0.50, "quality": 0.50})
        cat_supps = []

        for _, row in self.suppliers_df.iterrows():
            s = row['supplier_id']
            if s in self.active_suppliers and s not in result:
                if cat in str(row['categories']):
                    ot = float(row['on_time_pct']) / 100.0
                    q = float(row['quality_rating']) / 5.0
                    score = cat_weights.get("on_time", 0.50) * ot + cat_weights.get("quality", 0.50) * q
                    cat_supps.append((s, score))

        cat_supps.sort(key=lambda x: (-x[1], x[0]))
        for s, _ in cat_supps:
            result.append(s)
            if len(result) >= count_needed:
                break

        return result

    def process_batch(self, pr_lines: List[PRLineInput], policy_override: Optional[Dict[str, Any]] = None) -> List[PRDecisionOutput]:
        """
        Executes the Corvo Procurement Policy pipeline on a batch of PR lines.
        Outputs exactly 1 row per PR line with the 12 required columns.
        """
        policy = policy_override or self.policy
        params = policy.get("parameters", {})
        anti_splitting_window = params.get("anti_splitting_window_days", 14)
        need_by_window = params.get("need_by_window_days", 7)
        price_history_days = params.get("price_history_days", 365)
        po_window_hours = params.get("po_consolidation_window_hours", 24)

        self.reset_contract_consumed()

        # Step 1: Item Identification and Anomaly Detection
        parsed_lines = []
        for line in pr_lines:
            line_dict = line.model_dump() if hasattr(line, "model_dump") else dict(line)
            
            # Normalize plant
            line_dict['plant'] = str(line_dict.get('plant', '')).strip().upper()
            
            # Robust item code resolution
            code = line_dict.get('item_code')
            if code and str(code).strip():
                candidate_code = str(code).strip().upper()
                if candidate_code in self.item_map:
                    resolved_code = candidate_code
                else:
                    # Item code not in catalog, fallback to fuzzy description match
                    f_code, _, _ = self.item_matcher.match(line_dict.get('description', ''))
                    resolved_code = f_code
            else:
                resolved_code, _, _ = self.item_matcher.match(line_dict.get('description', ''))
            
            line_dict['resolved_item_code'] = resolved_code
            
            # Robust date parsing
            line_dict['created_dt'] = pd.to_datetime(str(line_dict.get('created_at', '')).strip(), errors='coerce')
            line_dict['need_by_dt'] = pd.to_datetime(str(line_dict.get('need_by_date', '')).strip(), errors='coerce')
            parsed_lines.append(line_dict)

        # Detect edge cases & unprocessable lines (zero qty, invalid dates, invalid plant, suspicious duplicate submissions)
        suspicious_duplicates = set()
        for i in range(len(parsed_lines)):
            for j in range(i + 1, len(parsed_lines)):
                l1 = parsed_lines[i]
                l2 = parsed_lines[j]
                if (pd.notna(l1['created_dt']) and pd.notna(l2['created_dt']) and
                    l1['requester'] == l2['requester'] and
                    l1['plant'] == l2['plant'] and
                    l1['resolved_item_code'] == l2['resolved_item_code'] and
                    l1['need_by_date'] == l2['need_by_date'] and
                    abs((l1['created_dt'] - l2['created_dt']).total_seconds()) <= 900 and
                    l1['department'] != l2['department']):
                    suspicious_duplicates.add((l1['pr_no'], l1['pr_line']))
                    suspicious_duplicates.add((l2['pr_no'], l2['pr_line']))

        processable_lines = []
        unprocessed_outputs = []

        for line in parsed_lines:
            key = (line['pr_no'], line['pr_line'])
            if pd.isna(line['created_dt']) or pd.isna(line['need_by_dt']):
                unprocessed_outputs.append(PRDecisionOutput(
                    pr_no=line['pr_no'],
                    pr_line=line['pr_line'],
                    resolved_item_code=line['resolved_item_code'],
                    group_id="REQ-DISCARDED",
                    po_id="",
                    decision="SOURCING_REQUEST",
                    route="NOT_PROCESSED",
                    supplier_id="",
                    unit_price=None,
                    group_value_inr=0.0,
                    suggested_supplier_ids="",
                    policy_version=policy.get("version", "v5.0"),
                    reason="Invalid date format: created_at or need_by_date could not be parsed"
                ))
            elif line['quantity'] <= 0:
                unprocessed_outputs.append(PRDecisionOutput(
                    pr_no=line['pr_no'],
                    pr_line=line['pr_line'],
                    resolved_item_code=line['resolved_item_code'],
                    group_id="REQ-DISCARDED",
                    po_id="",
                    decision="SOURCING_REQUEST",
                    route="NOT_PROCESSED",
                    supplier_id="",
                    unit_price=None,
                    group_value_inr=0.0,
                    suggested_supplier_ids="",
                    policy_version=policy.get("version", "v5.0"),
                    reason="Invalid quantity: Requisition quantity must be greater than zero"
                ))
            elif line['plant'] not in self.valid_plants:
                unprocessed_outputs.append(PRDecisionOutput(
                    pr_no=line['pr_no'],
                    pr_line=line['pr_line'],
                    resolved_item_code=line['resolved_item_code'],
                    group_id="REQ-DISCARDED",
                    po_id="",
                    decision="SOURCING_REQUEST",
                    route="NOT_PROCESSED",
                    supplier_id="",
                    unit_price=None,
                    group_value_inr=0.0,
                    suggested_supplier_ids="",
                    policy_version=policy.get("version", "v5.0"),
                    reason=f"Invalid plant: '{line['plant']}' not in Corvo registered plants ({', '.join(sorted(self.valid_plants))})"
                ))
            elif key in suspicious_duplicates:
                unprocessed_outputs.append(PRDecisionOutput(
                    pr_no=line['pr_no'],
                    pr_line=line['pr_line'],
                    resolved_item_code=line['resolved_item_code'],
                    group_id="REQ-DISCARDED",
                    po_id="",
                    decision="SOURCING_REQUEST",
                    route="NOT_PROCESSED",
                    supplier_id="",
                    unit_price=None,
                    group_value_inr=0.0,
                    suggested_supplier_ids="",
                    policy_version=policy.get("version", "v5.0"),
                    reason="Flagged as suspicious duplicate requisition: Identical item and need-by date submitted with conflicting departments"
                ))
            else:
                processable_lines.append(line)

        # Sort order: created_at ASC, pr_no ASC, pr_line ASC (Clause 2.2)
        processable_lines.sort(key=lambda x: (x['created_dt'], x['pr_no'], x['pr_line']))

        # Step 2: Clubbing Requirements / Anti-Splitting (Clause 2)
        groups = []
        for line in processable_lines:
            item_code = line['resolved_item_code']
            plant = line['plant']
            c_dt = line['created_dt']
            nb_dt = line['need_by_dt']

            joined_group = None
            if item_code != "NEW":
                for g in groups:
                    if g['item_code'] == item_code and g['plant'] == plant:
                        days_created = (c_dt - g['first_created']).total_seconds() / 86400.0
                        days_need_by = abs((nb_dt - g['first_need_by']).total_seconds() / 86400.0)
                        if 0 <= days_created <= anti_splitting_window and days_need_by <= need_by_window:
                            joined_group = g
                            break

            if joined_group:
                joined_group['lines'].append(line)
            else:
                gid = f"REQ-{len(groups)+1:04d}"
                groups.append({
                    'group_id': gid,
                    'item_code': item_code,
                    'plant': plant,
                    'first_created': c_dt,
                    'first_need_by': nb_dt,
                    'lines': [line]
                })

        # Process each Requirement Group
        req_results = []
        for g in groups:
            item_code = g['item_code']
            plant = g['plant']
            c_dt = g['first_created']
            req_date = c_dt.floor('D')
            total_qty = sum(r['quantity'] for r in g['lines'])
            is_emergency = any(str(r.get('urgency', '')).strip().lower() == 'emergency' for r in g['lines'])

            # New Item handling (Clause 1.2)
            if item_code == "NEW":
                est_p = g['lines'][0].get('estimated_unit_price')
                val = total_qty * (float(est_p) if est_p is not None and pd.notna(est_p) else 0.0)
                req_results.append({
                    'group': g,
                    'decision': 'SOURCING_REQUEST',
                    'route': 'NEW_ITEM_SOURCING',
                    'supplier_id': "",
                    'unit_price': None,
                    'group_value_inr': val,
                    'suggested_suppliers': [],
                    'policy_version': policy.get('version', 'v5.0'),
                    'reason': 'Clause 1.2: New item not in master, sent to sourcing'
                })
                continue

            itype = self.item_map[item_code]['item_type']
            category = self.item_map[item_code]['category']

            # Step 4: Contract Evaluation
            c_item = self.contract_lines_df[self.contract_lines_df['item_code'] == item_code].merge(
                self.contract_register_df, on='contract_id'
            )
            c_item['start_dt'] = pd.to_datetime(c_item['start_date'])
            c_item['end_dt'] = pd.to_datetime(c_item['end_date'])

            applicable_contracts = []
            for _, crow in c_item.iterrows():
                cid = crow['contract_id']
                supp = crow['supplier_id']
                if supp in self.active_suppliers and crow['start_dt'] <= req_date <= crow['end_dt']:
                    rate = float(crow['rate'])
                    cap = float(crow['value_cap'])
                    consumed = self.contract_consumed[cid]
                    has_ceiling = (consumed + total_qty * rate) <= cap
                    applicable_contracts.append({
                        'contract_id': cid,
                        'supplier_id': supp,
                        'supplier_name': crow['supplier_name'],
                        'rate': rate,
                        'cap': cap,
                        'consumed': consumed,
                        'has_ceiling': has_ceiling
                    })

            valid_with_ceiling = [c for c in applicable_contracts if c['has_ceiling']]

            # Step 3: Valuation of Requirement (Clause 3)
            if valid_with_ceiling:
                valid_with_ceiling.sort(key=lambda x: x['rate'])
                unit_price_val = valid_with_ceiling[0]['rate']
            elif applicable_contracts:
                applicable_contracts.sort(key=lambda x: x['rate'])
                unit_price_val = applicable_contracts[0]['rate']
            else:
                po_365 = self.po_history_df[
                    (self.po_history_df['item_code'] == item_code) &
                    (self.po_history_df['po_dt'] <= req_date) &
                    (self.po_history_df['po_dt'] >= req_date - timedelta(days=price_history_days))
                ]
                if len(po_365) > 0:
                    last_po = po_365.sort_values(by=['po_dt', 'po_number'], ascending=[False, False]).iloc[0]
                    unit_price_val = float(last_po['unit_price'])
                else:
                    unit_price_val = float(self.item_map[item_code]['standard_price'])

            req_value = total_qty * unit_price_val

            # Check purchase history from Active supplier in 365 days
            po_365_active = self.po_history_df[
                (self.po_history_df['item_code'] == item_code) &
                (self.po_history_df['po_dt'] <= req_date) &
                (self.po_history_df['po_dt'] >= req_date - timedelta(days=price_history_days)) &
                (self.po_history_df['supplier_id'].isin(self.active_suppliers))
            ]
            bought_365_active = len(po_365_active) > 0

            # Step 5: Policy-as-Data Dynamic Decision Evaluation
            eval_context = {
                'item_type': itype,
                'category': category,
                'plant': plant,
                'value': req_value,
                'total_quantity': total_qty,
                'is_emergency': is_emergency,
                'contract_available': len(valid_with_ceiling) > 0,
                'bought_in_365d_active': bought_365_active
            }

            matched_rule = None
            for rule in policy.get("rules", []):
                if evaluate_condition(rule.get("condition", {}), eval_context):
                    matched_rule = rule
                    break

            if matched_rule is None:
                decision = "SOURCING_REQUEST"
                route = "RFQ"
                suggested = self.get_sourcing_suggestions(item_code, req_date, 3)
                reason = "Default fallback sourcing"
                supp_id = ""
                po_price = None
            else:
                decision = matched_rule["decision"]
                route = matched_rule["route"]
                supp_id = ""
                po_price = None
                suggested = []
                reason = matched_rule.get("reason_template", "")

                if route == "CONTRACT_PO":
                    chosen_c = valid_with_ceiling[0]
                    supp_id = chosen_c['supplier_id']
                    po_price = chosen_c['rate']
                    self.contract_consumed[chosen_c['contract_id']] += total_qty * chosen_c['rate']
                    reason = reason.format(contract_id=chosen_c['contract_id'])
                elif route in ["EMERGENCY_PO", "SPOT_PO"]:
                    pref = self.get_preferred_suppliers(item_code, req_date)
                    if pref:
                        supp_id = pref[0]['supplier_id']
                        po_price = pref[0]['reference_price']
                    else:
                        decision = "SOURCING_REQUEST"
                        route = "RFQ"
                        suggested = self.get_sourcing_suggestions(item_code, req_date, 3)
                        reason = "No active preferred supplier, routing to RFQ"
                elif decision == "SOURCING_REQUEST":
                    suggest_count = matched_rule.get("suggest_count", 3)
                    suggested = self.get_sourcing_suggestions(item_code, req_date, suggest_count)

            req_results.append({
                'group': g,
                'decision': decision,
                'route': route,
                'supplier_id': supp_id,
                'unit_price': po_price,
                'group_value_inr': req_value,
                'suggested_suppliers': suggested,
                'policy_version': policy.get('version', 'v5.0'),
                'reason': reason
            })

        # Step 7: PO Consolidation (Clause 7)
        po_list = []
        for res in req_results:
            if res['decision'] == 'PO':
                g = res['group']
                supp = res['supplier_id']
                plant = g['plant']
                route = res['route']
                c_dt = g['first_created']

                joined_po = None
                for p in po_list:
                    if p['supplier_id'] == supp and p['plant'] == plant and p['route'] == route:
                        hours_diff = (c_dt - p['first_created']).total_seconds() / 3600.0
                        if 0 <= hours_diff <= po_window_hours:
                            joined_po = p
                            break

                if joined_po:
                    joined_po['reqs'].append(res)
                    res['po_id'] = joined_po['po_id']
                else:
                    po_num = f"PO-{len(po_list)+1:04d}"
                    new_po = {
                        'po_id': po_num,
                        'supplier_id': supp,
                        'plant': plant,
                        'route': route,
                        'first_created': c_dt,
                        'reqs': [res]
                    }
                    po_list.append(new_po)
                    res['po_id'] = po_num
            else:
                res['po_id'] = ""

        # Build output rows
        output_rows: List[PRDecisionOutput] = []
        for res in req_results:
            g = res['group']
            for line in g['lines']:
                output_rows.append(PRDecisionOutput(
                    pr_no=line['pr_no'],
                    pr_line=line['pr_line'],
                    resolved_item_code=line['resolved_item_code'],
                    group_id=g['group_id'],
                    po_id=res['po_id'],
                    decision=res['decision'],
                    route=res['route'],
                    supplier_id=res['supplier_id'],
                    unit_price=round(res['unit_price'], 2) if res['unit_price'] is not None else None,
                    group_value_inr=round(res['group_value_inr'], 2),
                    suggested_supplier_ids=";".join(res['suggested_suppliers']),
                    policy_version=res['policy_version'],
                    reason=res['reason']
                ))

        # Add unprocessed rows
        output_rows.extend(unprocessed_outputs)

        # Re-sort to match original PR batch line order
        input_order_map = {(l.pr_no, l.pr_line): idx for idx, l in enumerate(pr_lines)}
        output_rows.sort(key=lambda x: input_order_map.get((x.pr_no, x.pr_line), 0))

        return output_rows
