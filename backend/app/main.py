import io
import csv
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path

from .config import (
    SAMPLE_PR_BATCH_CSV, ITEM_MASTER_CSV, SUPPLIER_MASTER_CSV, CONTRACTS_PDF_DIR, BASE_DIR
)
from .schemas import (
    PRLineInput, PRDecisionOutput, PolicySchema, PolicyDiff, BuyerRequirementView
)
from .decision_engine import DecisionEngine
from .policy_engine import PolicyManager
from .chat_intake import ChatIntakeAssistant
from .pdf_parser import parse_contract_pdf, extract_text_from_pdf
from .db import init_db, log_audit, get_audit_logs, get_db_connection

app = FastAPI(
    title="Corvo Engineering PR-to-PO Procurement Copilot",
    description="Production-grade, policy-driven procurement engine and buyer workspace",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for currently loaded requirements / batch decisions
CURRENT_BATCH_RESULTS: List[PRDecisionOutput] = []
CURRENT_REQUIREMENTS_MAP: Dict[str, Dict[str, Any]] = {}
_chat_assistant = None  # Lazy-initialized after DB is seeded in startup_event

def get_chat_assistant() -> ChatIntakeAssistant:
    global _chat_assistant
    if _chat_assistant is None:
        _chat_assistant = ChatIntakeAssistant()
    return _chat_assistant

@app.on_event("startup")
def startup_event():
    init_db()  # Creates tables AND seeds master data from seed_data.py
    PolicyManager.ensure_default_policy()

    # Optional: Download data bundle from URL (DATA_DOWNLOAD_URL env var) for supplemental files
    data_url = os.environ.get("DATA_DOWNLOAD_URL")
    if data_url:
        try:
            import urllib.request, io, tarfile, zipfile
            print(f"Downloading supplemental data from {data_url} ...")
            with urllib.request.urlopen(data_url, timeout=60) as resp:
                raw = resp.read()
            if data_url.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    zf.extractall(path=str(BASE_DIR))
            else:
                with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
                    tar.extractall(path=str(BASE_DIR))
            print("Successfully extracted supplemental data bundle.")
        except Exception as e:
            print(f"Error downloading DATA_DOWNLOAD_URL: {e}")

    # Preload sample PR batch into Buyer Workspace if available on disk
    if os.path.exists(SAMPLE_PR_BATCH_CSV):
        try:
            with open(SAMPLE_PR_BATCH_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                lines = [PRLineInput(**r) for r in reader]
                engine = DecisionEngine()
                global CURRENT_BATCH_RESULTS, CURRENT_REQUIREMENTS_MAP
                CURRENT_BATCH_RESULTS = engine.process_batch(lines)
                build_requirements_cache(lines, CURRENT_BATCH_RESULTS, engine)
                print(f"[Startup] Preloaded {len(CURRENT_BATCH_RESULTS)} decisions from sample PR batch.")
        except Exception as e:
            print(f"[Startup] No sample PR batch preloaded: {e}")

def build_requirements_cache(input_lines: List[PRLineInput], decisions: List[PRDecisionOutput], engine: DecisionEngine):
    global CURRENT_REQUIREMENTS_MAP
    CURRENT_REQUIREMENTS_MAP.clear()
    
    # Group inputs by group_id
    inputs_by_key = {(l.pr_no, l.pr_line): l for l in input_lines}
    
    for d in decisions:
        gid = d.group_id
        if gid not in CURRENT_REQUIREMENTS_MAP:
            item_info = engine.item_matcher.get_by_code(d.resolved_item_code) if d.resolved_item_code != "NEW" else None
            supp_name = engine.supplier_map.get(d.supplier_id, {}).get("name") if d.supplier_id else ""
            
            CURRENT_REQUIREMENTS_MAP[gid] = {
                "group_id": gid,
                "item_code": d.resolved_item_code,
                "item_description": item_info["description"] if item_info else ("New Item" if d.resolved_item_code == "NEW" else d.resolved_item_code),
                "category": item_info["category"] if item_info else "Uncategorized",
                "item_type": item_info["item_type"] if item_info else "New Material",
                "plant": inputs_by_key.get((d.pr_no, d.pr_line), input_lines[0]).plant,
                "total_quantity": 0,
                "uom": item_info["uom"] if item_info else "NOS",
                "first_created_at": inputs_by_key.get((d.pr_no, d.pr_line), input_lines[0]).created_at,
                "first_need_by_date": inputs_by_key.get((d.pr_no, d.pr_line), input_lines[0]).need_by_date,
                "is_emergency": False,
                "group_value_inr": d.group_value_inr,
                "unit_price": d.unit_price,
                "decision": d.decision,
                "route": d.route,
                "po_id": d.po_id,
                "supplier_id": d.supplier_id,
                "supplier_name": supp_name,
                "suggested_suppliers": [
                    {"supplier_id": sid, "name": engine.supplier_map.get(sid, {}).get("name", sid)}
                    for sid in d.suggested_supplier_ids.split(";") if sid
                ],
                "policy_version": d.policy_version,
                "reason": d.reason,
                "status": "PENDING",
                "override_reason": None,
                "action_by": None,
                "action_at": None,
                "pr_lines": []
            }
        
        req = CURRENT_REQUIREMENTS_MAP[gid]
        inp = inputs_by_key.get((d.pr_no, d.pr_line))
        if inp:
            req["total_quantity"] += inp.quantity
            if inp.urgency.lower() == "emergency":
                req["is_emergency"] = True
            req["pr_lines"].append(inp.model_dump())

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_policy": PolicyManager.get_active_policy().get("version", "v5.0"),
        "master_data_loaded": True  # Always true: seeded from seed_data.py at init_db()
    }

@app.post("/api/admin/bootstrap-data")
async def bootstrap_data_endpoint(file: UploadFile = File(...)):
    """
    Ingests a zip or tar.gz archive containing the task data directory.
    Enables zero-downtime data initialization on public deployments without committing files to git.
    """
    import zipfile, tarfile
    content = await file.read()
    filename = file.filename.lower()
    
    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                z.extractall(path=str(BASE_DIR))
        elif filename.endswith((".tar.gz", ".tgz", ".tar")):
            with tarfile.open(fileobj=io.BytesIO(content)) as t:
                t.extractall(path=str(BASE_DIR))
        else:
            raise HTTPException(status_code=400, detail="File must be a .zip or .tar.gz archive containing data/")
        
        # Reload sample batch if available
        if os.path.exists(SAMPLE_PR_BATCH_CSV) and os.path.exists(ITEM_MASTER_CSV):
            with open(SAMPLE_PR_BATCH_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                lines = [PRLineInput(**r) for r in reader]
                engine = DecisionEngine()
                global CURRENT_BATCH_RESULTS, CURRENT_REQUIREMENTS_MAP
                CURRENT_BATCH_RESULTS = engine.process_batch(lines)
                build_requirements_cache(lines, CURRENT_BATCH_RESULTS, engine)

        return {"message": "Data bootstrap archive extracted and loaded successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract bootstrap data: {str(e)}")

# 1. Batch Processing Endpoint
@app.post("/api/process-batch")
async def process_batch_endpoint(file: Optional[UploadFile] = File(None), lines_json: Optional[str] = Form(None)):
    """
    Accepts CSV upload or JSON input of PR lines and evaluates them through the active policy.
    Returns 12-column decision rows and batch metrics.
    """
    input_lines = []
    if file:
        content = await file.read()
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            input_lines.append(PRLineInput(**row))
    elif lines_json:
        data = json.loads(lines_json)
        input_lines = [PRLineInput(**r) for r in data]
    else:
        raise HTTPException(status_code=400, detail="Must provide CSV file or lines_json")

    if not input_lines:
        raise HTTPException(status_code=400, detail="No PR lines found in input")

    engine = DecisionEngine()
    decisions = engine.process_batch(input_lines)

    global CURRENT_BATCH_RESULTS
    CURRENT_BATCH_RESULTS = decisions
    build_requirements_cache(input_lines, decisions, engine)

    # Calculate metrics
    total_lines = len(decisions)
    unique_groups = len(set(d.group_id for d in decisions))
    po_count = len(set(d.po_id for d in decisions if d.po_id))
    total_val = sum(req["group_value_inr"] for req in CURRENT_REQUIREMENTS_MAP.values())
    
    route_counts = {}
    for d in decisions:
        route_counts[d.route] = route_counts.get(d.route, 0) + 1

    log_audit(
        user_id="Procurement Officer",
        action="PROCESS_BATCH",
        target_type="BATCH",
        target_id=f"BATCH-{datetime.now().strftime('%Y%m%d%H%M')}",
        details={"lines": total_lines, "requirements": unique_groups, "pos": po_count}
    )

    return {
        "metrics": {
            "total_pr_lines": total_lines,
            "total_requirements": unique_groups,
            "total_pos_formed": po_count,
            "total_value_inr": round(total_val, 2),
            "route_breakdown": route_counts,
            "policy_version": PolicyManager.get_active_policy().get("version", "v5.0")
        },
        "decisions": [d.model_dump() for d in decisions]
    }

# 2. Export Decisions CSV
@app.get("/api/export-decisions")
def export_decisions_csv():
    """
    Downloads decisions as CSV matching the exact required 12-column format.
    """
    if not CURRENT_BATCH_RESULTS:
        raise HTTPException(status_code=404, detail="No batch decisions available. Process a batch first.")

    output = io.StringIO()
    fieldnames = [
        "pr_no", "pr_line", "resolved_item_code", "group_id", "po_id",
        "decision", "route", "supplier_id", "unit_price", "group_value_inr",
        "suggested_supplier_ids", "policy_version", "reason"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for d in CURRENT_BATCH_RESULTS:
        row = d.model_dump()
        if row["unit_price"] is None:
            row["unit_price"] = ""
        writer.writerow(row)

    output.seek(0)
    filename = f"corvo_procurement_decisions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# 3. Preferred Supplier List Export
@app.get("/api/suppliers/preferred")
def export_preferred_suppliers(
    as_of_date: str = Query("2026-11-01", description="Date YYYY-MM-DD as of which to compute ranking"),
    item_code: Optional[str] = Query(None),
    format: str = Query("json")
):
    """
    Builds the preferred supplier list for every item (or chosen item) as of a date.
    Exports as CSV (item_code, rank, supplier_id, reference_price, top 3) or JSON.
    """
    engine = DecisionEngine()
    as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")

    target_items = [item_code] if item_code else sorted(list(engine.item_map.keys()))
    all_rows = []

    for icode in target_items:
        ranked = engine.get_preferred_suppliers(icode, as_of_dt)
        for supp in ranked:
            all_rows.append({
                "item_code": icode,
                "rank": supp["rank"],
                "supplier_id": supp["supplier_id"],
                "supplier_name": supp["supplier_name"],
                "reference_price": round(supp["reference_price"], 2) if supp["reference_price"] else None,
                "score": supp["score"],
                "recency": supp["recency"],
                "po_count": supp["po_count"],
                "has_contract": supp["has_contract"],
                "on_time_pct": supp["on_time_pct"],
                "quality_rating": supp["quality_rating"]
            })

    if format == "csv":
        # Required format: item_code, rank, supplier_id, reference_price (top 3 per item)
        output = io.StringIO()
        fieldnames = ["item_code", "rank", "supplier_id", "reference_price"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for r in all_rows:
            if r["rank"] <= 3:
                writer.writerow({
                    "item_code": r["item_code"],
                    "rank": r["rank"],
                    "supplier_id": r["supplier_id"],
                    "reference_price": r["reference_price"] or ""
                })

        output.seek(0)
        filename = f"preferred_suppliers_{as_of_date}.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    return {"as_of_date": as_of_date, "count": len(all_rows), "suppliers": all_rows}

# 4. Buyer Workspace Endpoints
@app.get("/api/buyer/requirements")
def get_buyer_requirements():
    return list(CURRENT_REQUIREMENTS_MAP.values())

@app.post("/api/buyer/approve/{group_id}")
def approve_requirement(group_id: str, action_by: str = Body("Buyer Lead", embed=True)):
    if group_id not in CURRENT_REQUIREMENTS_MAP:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    req = CURRENT_REQUIREMENTS_MAP[group_id]
    req["status"] = "APPROVED"
    req["action_by"] = action_by
    req["action_at"] = datetime.now().isoformat()

    log_audit(
        user_id=action_by,
        action="APPROVE_REQUIREMENT",
        target_type="REQUIREMENT",
        target_id=group_id,
        details={"route": req["route"], "po_id": req["po_id"], "value": req["group_value_inr"]}
    )
    return {"message": "Requirement approved successfully", "requirement": req}

@app.post("/api/buyer/override/{group_id}")
def override_requirement(
    group_id: str,
    override_reason: str = Body(..., embed=True),
    new_route: Optional[str] = Body(None, embed=True),
    new_supplier_id: Optional[str] = Body(None, embed=True),
    new_price: Optional[float] = Body(None, embed=True),
    action_by: str = Body("Buyer Lead", embed=True)
):
    if not override_reason or not override_reason.strip():
        raise HTTPException(status_code=400, detail="Mandatory override explanation comment is required.")

    if group_id not in CURRENT_REQUIREMENTS_MAP:
        raise HTTPException(status_code=404, detail="Requirement not found")

    req = CURRENT_REQUIREMENTS_MAP[group_id]
    req["status"] = "OVERRIDDEN"
    req["override_reason"] = override_reason.strip()
    req["action_by"] = action_by
    req["action_at"] = datetime.now().isoformat()

    if new_route:
        req["route"] = new_route
    if new_supplier_id:
        req["supplier_id"] = new_supplier_id
    if new_price is not None:
        req["unit_price"] = new_price
        req["group_value_inr"] = req["total_quantity"] * new_price

    log_audit(
        user_id=action_by,
        action="OVERRIDE_REQUIREMENT",
        target_type="REQUIREMENT",
        target_id=group_id,
        details={
            "override_reason": override_reason,
            "new_route": new_route,
            "new_supplier_id": new_supplier_id,
            "new_price": new_price
        }
    )
    return {"message": "Requirement overridden successfully", "requirement": req}

# 5. Policy Management Endpoints
@app.get("/api/policy/active")
def get_active_policy():
    return PolicyManager.get_active_policy()

@app.get("/api/policy/history")
def list_policy_history():
    return PolicyManager.list_policies()

@app.post("/api/policy/amend-preview")
async def preview_policy_amendment(file: Optional[UploadFile] = File(None), text_description: Optional[str] = Form(None)):
    """
    Parses policy amendment text/PDF, computes plain language diffs, and returns proposed policy.
    """
    doc_text = ""
    if file:
        content = await file.read()
        if file.filename.lower().endswith(".pdf"):
            doc_text = extract_text_from_pdf(content)
        else:
            doc_text = content.decode("utf-8")
    elif text_description:
        doc_text = text_description
    else:
        raise HTTPException(status_code=400, detail="Must provide an amendment document file or text description")

    current = PolicyManager.get_active_policy()
    proposed, diffs = PolicyManager.parse_amendment_text(doc_text, current)

    return {
        "old_version": current.get("version", "v5.0"),
        "new_version": proposed.get("version", "v5.1"),
        "effective_date": proposed.get("effective_date"),
        "diffs": diffs,
        "proposed_policy": proposed
    }

@app.post("/api/policy/activate")
def activate_policy(payload: Dict[str, Any] = Body(...), user_id: str = Body("Procurement Officer", embed=True)):
    """
    Activates the proposed policy version without modifying code or restarting the application.
    """
    policy_data = payload.get("proposed_policy", payload)
    activated = PolicyManager.save_and_activate_policy(policy_data, user_id=user_id)
    return {"message": f"Policy {activated['version']} activated successfully!", "policy": activated}

# 6. Chat PR Intake Endpoint
@app.post("/api/chat/message")
def chat_message(
    message: str = Body(..., embed=True),
    state: Optional[Dict[str, Any]] = Body(None, embed=True),
    requester: str = Body("A. Kumar", embed=True)
):
    reply, new_state = get_chat_assistant().handle_message(message, state=state, requester=requester)
    return {"reply": reply, "state": new_state}

# 7. Upload signed contract PDF
@app.post("/api/contracts/upload-pdf")
async def upload_contract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    content = await file.read()
    parsed = parse_contract_pdf(content)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO contracts_extracted
    (contract_id, supplier_id, supplier_name, start_date, end_date, value_cap, consumed_value, lines_json, source, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        parsed["contract_id"],
        parsed["supplier_id"],
        parsed["supplier_name"],
        parsed["start_date"],
        parsed["end_date"],
        parsed["value_cap"],
        0.0,
        json.dumps(parsed["lines"]),
        file.filename,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    log_audit(
        user_id="Procurement Officer",
        action="UPLOAD_CONTRACT_PDF",
        target_type="CONTRACT",
        target_id=parsed["contract_id"],
        details={"supplier": parsed["supplier_name"], "cap": parsed["value_cap"], "lines": len(parsed["lines"])}
    )

    return {"message": f"Contract {parsed['contract_id']} ingested successfully", "contract": parsed}

# 8. Audit Logs Endpoint
@app.get("/api/audit-logs")
def fetch_audit_logs(limit: int = 100):
    return get_audit_logs(limit=limit)

# Serve built frontend in production if available
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")

