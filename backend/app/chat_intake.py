import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from .item_matcher import ItemMatcher
from .config import ITEM_MASTER_CSV
from .schemas import ChatPRState, PRLineInput
from .decision_engine import DecisionEngine
from .db import get_db_connection, log_audit

class ChatIntakeAssistant:
    def __init__(self):
        self.matcher = ItemMatcher(ITEM_MASTER_CSV)
        self.engine = DecisionEngine()

    def parse_user_input(self, text: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parses user message and fills missing slots:
        - item_code / item description
        - quantity
        - plant (PUN1, CHK1 / Pune, Chakan)
        - need_by_date (e.g. 'next Friday', 'by 2026-12-05', 'in 10 days')
        - urgency ('Urgent' / 'Emergency' / 'Normal')
        - estimated_unit_price (for new items)
        """
        if state is None:
            state = {
                "item_code": None,
                "matched_description": None,
                "raw_query": text,
                "quantity": None,
                "uom": "NOS",
                "plant": None,
                "need_by_date": None,
                "urgency": "Normal",
                "estimated_unit_price": None,
                "is_ready_to_create": False,
                "confirmed": False,
                "created_pr_no": None,
                "suggested_items": []
            }

        text_lower = text.lower().strip()

        # Confirmation detection
        if text_lower in ["yes", "confirm", "proceed", "yes please", "submit", "approved", "ok", "sure", "create"]:
            if state.get("is_ready_to_create") and not state.get("confirmed"):
                state["confirmed"] = True
                return state

        # 1. Quantity detection: e.g. "200 gloves", "15 nos", "qty 50", "need 10"
        qty_match = re.search(r'\b(?:need|buy|procure|order|quantity|qty)?\s*(\d+)\s*(?:nos|pcs|pieces|units|mtr|meters|kg|ltr|liters|pairs|qtr|box)?\b', text_lower)
        if qty_match and not state.get("quantity"):
            val = int(qty_match.group(1))
            if val > 0:
                state["quantity"] = val

        # 2. Plant detection:
        if "chakan" in text_lower or "chk1" in text_lower:
            state["plant"] = "CHK1"
        elif "bhosari" in text_lower or "pune" in text_lower or "pun1" in text_lower:
            state["plant"] = "PUN1"

        # 3. Urgency detection:
        if "emergency" in text_lower or "breakdown" in text_lower:
            state["urgency"] = "Emergency"
        elif "urgent" in text_lower or "asap" in text_lower:
            state["urgency"] = "Emergency"

        # 4. Need-by date parsing:
        # e.g. "2026-11-28", "28 Nov", "next friday", "in 7 days", "tomorrow"
        date_explicit = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
        if date_explicit:
            state["need_by_date"] = date_explicit.group(1)
        elif "next friday" in text_lower:
            # calculate next Friday from current date
            now = datetime.now()
            days_ahead = 4 - now.weekday()  # Friday is 4
            if days_ahead <= 0:
                days_ahead += 7
            state["need_by_date"] = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        elif "next week" in text_lower:
            state["need_by_date"] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        elif "tomorrow" in text_lower:
            state["need_by_date"] = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            in_days_match = re.search(r'in\s+(\d+)\s+days', text_lower)
            if in_days_match:
                days = int(in_days_match.group(1))
                state["need_by_date"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        # 5. Item matching (if not yet identified):
        if not state.get("item_code"):
            # Clean out plant and quantity words to isolate the item search term
            query_clean = re.sub(r'\b(need|buy|procure|order|quantity|qty|\d+|nos|pcs|for|at|by|in|days|chakan|pune|bhosari|chk1|pun1|next|friday|tomorrow|asap|urgent|emergency)\b', '', text_lower)
            query_clean = ' '.join(query_clean.split())
            if query_clean:
                code, info, score = self.matcher.match(query_clean)
                if code != "NEW" and info:
                    state["item_code"] = code
                    state["matched_description"] = info["description"]
                    state["uom"] = info["uom"]
                else:
                    suggestions = self.matcher.find_suggestions(query_clean)
                    if suggestions:
                        state["suggested_items"] = [s["description"] for s in suggestions]
                    state["item_code"] = "NEW"
                    state["matched_description"] = query_clean.title()

        # 6. Estimated price detection (if NEW item):
        if state.get("item_code") == "NEW" and not state.get("estimated_unit_price"):
            price_match = re.search(r'(?:price|rate|estimated|est|approx|rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)', text_lower)
            if price_match:
                state["estimated_unit_price"] = float(price_match.group(1).replace(",", ""))

        # Check completeness
        missing = []
        if not state.get("item_code"):
            missing.append("item description")
        if not state.get("quantity"):
            missing.append("quantity")
        if not state.get("plant"):
            missing.append("delivery plant (PUN1 / Bhosari or CHK1 / Chakan)")
        if not state.get("need_by_date"):
            missing.append("need-by date")
        if state.get("item_code") == "NEW" and not state.get("estimated_unit_price"):
            missing.append("estimated unit price (INR) for this new item")

        state["missing_fields"] = missing
        state["is_ready_to_create"] = (len(missing) == 0)

        return state

    def handle_message(self, user_message: str, state: Optional[Dict[str, Any]] = None, requester: str = "A. Kumar") -> Tuple[str, Dict[str, Any]]:
        state = self.parse_user_input(user_message, state)

        # 1. If user confirmed and is ready: create the PR
        if state.get("confirmed") and state.get("is_ready_to_create"):
            pr_no = f"PR-26-{datetime.now().strftime('%m%d%H%M')}"
            state["created_pr_no"] = pr_no
            
            # Evaluate PR line through DecisionEngine
            line_input = PRLineInput(
                pr_no=pr_no,
                pr_line=1,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
                requester=requester,
                department="Operations",
                plant=state["plant"],
                item_code=state["item_code"] if state["item_code"] != "NEW" else None,
                description=state["matched_description"],
                quantity=state["quantity"],
                uom=state.get("uom", "NOS"),
                estimated_unit_price=state.get("estimated_unit_price"),
                need_by_date=state["need_by_date"],
                urgency=state.get("urgency", "Normal")
            )
            decisions = self.engine.process_batch([line_input])
            dec = decisions[0] if decisions else None

            log_audit(
                user_id=requester,
                action="CREATE_PR_CHAT",
                target_type="PR",
                target_id=pr_no,
                details=state
            )

            response = f"✅ **Purchase Requisition {pr_no} created successfully!**\n\n"
            response += f"- **Item:** {state['matched_description']} ({state['item_code']})\n"
            response += f"- **Quantity:** {state['quantity']} {state.get('uom', 'NOS')}\n"
            response += f"- **Plant:** {state['plant']}\n"
            response += f"- **Need-by:** {state['need_by_date']}\n"
            response += f"- **Urgency:** {state['urgency']}\n\n"

            if dec:
                response += f"📋 **Procurement Decision Engine Route:** `{dec.route}` ({dec.decision})\n"
                response += f"- **Estimated Value:** ₹{dec.group_value_inr:,.2f}\n"
                if dec.supplier_id:
                    response += f"- **Selected Supplier:** {dec.supplier_id} @ ₹{dec.unit_price}\n"
                    response += f"- **Generated PO:** `{dec.po_id}`\n"
                elif dec.suggested_supplier_ids:
                    response += f"- **Suggested Suppliers for Sourcing:** {dec.suggested_supplier_ids}\n"
                response += f"- **Policy Clause:** {dec.reason} ({dec.policy_version})\n"

            return response, state

        # 2. If slots are missing, prompt user clearly
        if state["missing_fields"]:
            prompts = []
            if "item description" in state["missing_fields"]:
                prompts.append("Which item do you need?")
            if "quantity" in state["missing_fields"]:
                prompts.append("What quantity do you need?")
            if "delivery plant (PUN1 / Bhosari or CHK1 / Chakan)" in state["missing_fields"]:
                prompts.append("Which plant is this for? (PUN1 - Bhosari or CHK1 - Chakan)")
            if "need-by date" in state["missing_fields"]:
                prompts.append("What is your need-by date? (e.g., 'next Friday' or 'YYYY-MM-DD')")
            if "estimated unit price (INR) for this new item" in state["missing_fields"]:
                prompts.append(f"'{state['matched_description']}' is not in our item master and will be sourced as a NEW item. What is your estimated unit price (INR)?")

            reply = f"I've noted your request for **{state.get('matched_description') or 'your item'}**.\n\n"
            reply += "Could you please clarify:\n"
            for p in prompts:
                reply += f"- {p}\n"

            if state.get("suggested_items"):
                reply += f"\n💡 *Did you mean one of these existing items?* {', '.join(state['suggested_items'])}"

            return reply, state

        # 3. Ready to create: ask for confirmation
        state["is_ready_to_create"] = True
        uom_str = state.get("uom", "NOS")
        reply = (
            f"Please confirm your purchase requisition details:\n\n"
            f"- **Item:** {state['matched_description']} ({state['item_code']})\n"
            f"- **Quantity:** {state['quantity']} {uom_str}\n"
            f"- **Plant:** {state['plant']}\n"
            f"- **Need-By Date:** {state['need_by_date']}\n"
            f"- **Urgency:** {state['urgency']}\n"
        )
        if state['item_code'] == 'NEW':
            reply += f"- **Estimated Unit Price:** ₹{state.get('estimated_unit_price', 0):,.2f}\n"

        reply += "\nType **'Yes'** or **'Confirm'** to submit this requisition, or specify any changes."
        return reply, state

