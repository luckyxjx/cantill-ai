# Corvo PR-to-PO Procurement Copilot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18.3+-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6+-3178C6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4+-38B2AC.svg)](https://tailwindcss.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-17%20Passed%20(100%25)-brightgreen.svg)]()

A production-grade, policy-driven procurement web application built for **Corvo Engineering**. It transforms unstructured purchase requests into compliant, policy-governed Purchase Orders (POs) and Sourcing Requests (RFQs/RFPs) with absolute mathematical determinism and zero-code policy adaptability.

---

## Table of Contents
1. [Core Features](#core-features)
2. [Architecture Overview](#architecture-overview)
3. [Policy-as-Data Architecture](#policy-as-data-architecture)
4. [Quickstart (Docker & Manual)](#quickstart)
5. [Automated Verification & Unit Tests](#automated-verification--unit-tests)
6. [API Documentation](#api-documentation)
7. [Blind Test Execution Protocol](#blind-test-execution-protocol)
8. [Directory Structure](#directory-structure)
9. [Documentation References](#documentation-references)

---

## Core Features

- **Conversational Requester Intake**: Chat assistant guides employees through PR creation, extracts slots (item, quantity, plant [PUN1/CHK1], need-by date, urgency), handles conversational ambiguities, performs semantic item matching, renders interactive confirmation cards, and submits validated requisitions.
- **Deterministic 8-Clause Decision Engine**: Strictly implements Corvo Procurement Policy v5.0:
  1. *Clause 1 (Item Identification)*: Exact code lookup or token-set fuzzy matching against 73-item master; flags new items as `NEW_ITEM_SOURCING`.
  2. *Clause 2 (Clubbing / Anti-Splitting)*: Groups requisitions by same item and plant within 14-day creation and ±7-day need-by windows. Propagates Emergency urgency.
  3. *Clause 3 (Valuation)*: Multi-tier rate selection (valid rate contract rate $\rightarrow$ most recent PO in 365 days with same-day sequence tie-breaking $\rightarrow$ standard catalog price).
  4. *Clause 4 (Contract Ceiling Tracking)*: Evaluates applicability, validity dates, active supplier status, and dynamically tracks cumulative consumption against `value_cap`.
  5. *Clause 5 (Decision Routing)*: Rules 5.1–5.7 strictly prioritized (`CAPEX_SOURCING` $\rightarrow$ `CONTRACT_PO` $\rightarrow$ `EMERGENCY_PO` $\rightarrow$ `SPOT_PO` $\rightarrow$ `RFQ` $\rightarrow$ `RFP`). Blocked/Inactive suppliers are hard-filtered.
  6. *Clause 6 (Supplier Ranking & Sourcing)*: Bounded $[0.0, 1.0]$ multi-factor scoring (Recency, Frequency, Contract History, On-time %, Quality) matching official worked examples with 100% fidelity. Category top-up for RFQ/RFP quotes.
  7. *Clause 7 (PO Consolidation)*: Consolidates PO requirements by supplier, plant, route, and 24-hour creation window into multi-line POs (`PO-0001`, `PO-0002`, ...).
  8. *Clause 8 (Audit & Compliance)*: Every step captures citations, calculations, timestamps, and buyer interactions.
- **Policy-as-Data Engine**: Policy rules, financial thresholds, and condition trees are stored as versioned JSON schemas in SQLite. Procurement teams can upload amendment documents (PDF/Text) or type natural-language revisions, preview diffs in plain English, and activate new versions **without restarting or redeploying code**.
- **Buyer Workspace**: Cockpit for procurement officers to inspect clubbed requirements, examine policy citations, approve auto-generated POs/RFQs, or execute manual overrides with mandatory justification comments.
- **Signed Contract Ingestion**: Ingests structured CSV registers and extracts PDF-only executed contracts (`RC-2026-031.pdf`, `RC-2026-033.pdf`) via deterministic PyMuPDF parser.
- **Batch Processing & Export**: Batch CSV evaluation producing the exact 12-column compliance format and top-3 preferred supplier lists.

---

## Architecture Overview

```
                               ┌──────────────────────────────────────────────┐
                               │           React + Vite Frontend              │
                               │  • Requester Chat   • Policy Manager View    │
                               │  • Buyer Workspace  • Export & Audit Views   │
                               └──────────────────────┬───────────────────────┘
                                                      │ HTTP / REST
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │            FastAPI Backend Engine            │
                               │  • /api/chat        • /api/policies          │
                               │  • /api/buyer       • /api/process-batch     │
                               └───────┬──────────────┬──────────────┬────────┘
                                       │              │              │
                   ┌───────────────────┘              │              └───────────────────┐
                   ▼                                  ▼                                  ▼
      ┌─────────────────────────┐        ┌─────────────────────────┐        ┌─────────────────────────┐
      │  Policy-as-Data Engine  │        │     Decision Engine     │        │     PDF / Data Layer    │
      │ • Versioned Policy DB   │        │ • 8-Clause Corvo Policy │        │ • PyMuPDF Parser        │
      │ • AST Condition Eval    │        │ • Supplier Scoring (C6) │        │ • RapidFuzz Matcher     │
      │ • Plain-Text Diff View  │        │ • PO Consolidation (C7) │        │ • SQLite Persistence    │
      └─────────────────────────┘        └─────────────────────────┘        └─────────────────────────┘
```

---

## Policy-as-Data Architecture

Procurement rules change frequently (e.g., threshold shifts, mandatory RFQ quotas, category restrictions). Rather than hardcoding numbers into Python code:
1. **Schema Representation**: Rules are stored as an Abstract Syntax Tree (AST) in the `policies` database table.
2. **Evaluator**: `PolicyEngine` dynamically checks conditions against runtime requisition properties (`group_value_inr`, `item_type`, `has_valid_contract`, `has_recent_purchase`, `is_emergency`).
3. **Amendment Pipeline**:
   - An administrator uploads an amendment document (PDF/TXT) or enters text.
   - The engine parses parameter changes (e.g., "Clause 5.4 spot limit raised to ₹3,00,000").
   - A structured diff is shown to the user with old values, new values, and policy impact.
   - Upon one-click approval, version `v5.1` is activated immediately with effective timestamps.

---

## Quickstart

### Method 1: Single-Command Docker Compose (Recommended)

Ensure Docker and Docker Compose are installed and running:

```bash
docker compose up --build
```

The system will build the multi-stage image (frontend build + FastAPI runtime) and launch the application on **http://localhost:8000**.

- **Web Application UI**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### Method 2: Manual Local Setup (Development Mode)

#### 1. Backend Setup
```bash
# Ensure Python 3.11+ is installed
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the test suite to verify data & policy logic
python3 -m unittest backend/tests/test_worked_examples.py

# Start FastAPI backend server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup
In a separate terminal window:
```bash
cd frontend
npm install
npm run dev
```
Access the Vite dev server at **http://localhost:3000** (proxied to port 8000).

Or build the frontend to be served directly by FastAPI:
```bash
cd frontend
npm run build
```
FastAPI automatically serves the production bundle from `frontend/dist` at `http://localhost:8000`.

---

## Automated Verification & Unit Tests

The test suite in [backend/tests/test_worked_examples.py](file:///Users/lucky./VISUAL_PROJECTS/cantill/backend/tests/test_worked_examples.py) executes end-to-end verification of all official worked examples:

```bash
python3 -m unittest backend/tests/test_worked_examples.py
```

### Verified Test Coverage
- **Example 1**: Single standard item matching valid rate contract $\rightarrow$ `CONTRACT_PO`.
- **Example 2**: Item with contract out of ceiling room fallbacks to RFQ $\rightarrow$ `RFQ`.
- **Example 3**: Emergency requirement under ₹5,00,000 with active purchase history $\rightarrow$ `EMERGENCY_PO`.
- **Example 4**: Low value requisition under ₹2,00,000 with prior purchase $\rightarrow$ `SPOT_PO`.
- **Example 5**: High value material requirement exceeding ₹10,00,000 $\rightarrow$ `RFP`.
- **Example 6**: Anti-splitting clubbing across 2 PR lines within 14-day window $\rightarrow$ combined value forces `RFQ`.
- **Example 7**: Capital expenditure requisition routing to Capex workflow $\rightarrow$ `CAPEX_SOURCING`.
- **Example 8**: Novel catalog item non-existent in item master $\rightarrow$ `NEW_ITEM_SOURCING`.
- **Example 9**: Expired contract non-applicability falling back to RFQ.
- **Example 10**: Requisition for item never purchased in last 365 days under ₹10L $\rightarrow$ `RFQ`.
- **Example 11**: Sourcing request with same-day PO history tie-breaking and category top-up $\rightarrow$ `RFQ`.
- **Example 12**: Large value RFP requiring 5 supplier suggestions with category top-up $\rightarrow$ `RFP`.
- **Example 13**: PO Consolidation combining eligible requirements within 24 hours into multi-line POs.
- **Example 14**: Dynamic multi-period contract ceiling consumption across sequential PR batches.
- **Preferred Supplier Tables (Page 5)**: Exact mathematical reproduction of supplier scores and ranks for:
  - `ITM-1048` (Ball Bearing): S029 (0.886) > S030 (0.690)
  - `ITM-1036` (Pneumatic Cylinder): S023 (0.634) > S022 (0.499) > S024 (0.382)
  - `ITM-1016` (Hydraulic Hose): S009 (0.665) > S010 (0.481)

---

## API Documentation

| Endpoint | Method | Description |
|---|---|---|
| `POST /api/process-batch` | POST | Upload a PR batch CSV and process it through the active policy engine. Returns 12-column decisions and summary stats. |
| `GET /api/export-decisions` | GET | Download the processed decisions as a compliant 12-column CSV file. |
| `GET /api/export-preferred-suppliers` | GET | Download top-3 preferred suppliers for all catalog items evaluated as of a target date. |
| `POST /api/chat/message` | POST | Conversational endpoint for requester chat intake with slot filling and PR confirmation. |
| `GET /api/policies/active` | GET | Fetch the currently active policy version, metadata, and JSON rules AST. |
| `POST /api/policies/amend/preview` | POST | Upload amendment text or PDF file to generate a structured plain-language diff preview. |
| `POST /api/policies/amend/activate` | POST | Activate a proposed policy amendment without restarting the server. |
| `GET /api/buyer/requirements` | GET | Fetch all grouped requirements for buyer review with policy citations. |
| `POST /api/buyer/approve` | POST | Approve an auto-routed requirement into an official PO or Sourcing Event. |
| `POST /api/buyer/override` | POST | Buyer override of route/supplier with mandatory audit reason. |
| `GET /api/audit-logs` | GET | Comprehensive queryable audit trail of all policy decisions, overrides, and activations. |

---

## Blind Test Execution Protocol

During the 2-hour evaluation window, execute the following steps:

### Step 1: Run 1 (Baseline Policy v5.0)
1. Verify policy `v5.0` is active:
   - Check UI header badge: **Active Policy: Corvo Procurement Policy v5.0**.
2. Run the provided baseline batch through the system:
   ```bash
   curl -X POST "http://localhost:8000/api/process-batch" \
     -F "file=@pr_batches/sample_pr_batch.csv"
   ```
3. Export decisions:
   - Click **Export Decisions (CSV)** in the UI, or fetch:
   ```bash
   curl -o submission/run_1_decisions_v5.0.csv "http://localhost:8000/api/export-decisions"
   ```
4. Export preferred supplier rankings as of 2026-11-01:
   ```bash
   curl -o submission/preferred_suppliers_2026-11-01.csv "http://localhost:8000/api/export-preferred-suppliers?as_of_date=2026-11-01"
   ```

### Step 2: Policy Amendment (Transition to v5.1)
1. Open the **Policy Manager** tab in the UI (`/policies`).
2. Upload the newly provided Policy Amendment PDF / document, or paste the amendment text.
3. Review the **Visual Diff**:
   - Check the side-by-side comparison of modified clauses, updated threshold limits, and rule ordering.
4. Click **Activate Policy v5.1**.
   - The system writes the new version to the database and sets it active immediately.
   - Zero code changes and zero server downtime required.

### Step 3: Run 2 (Amended Policy v5.1)
1. In the **Buyer Workspace** or **Requester Intake**, upload the new test PR batch CSV (`new_pr_batch.csv`).
2. Process the batch:
   ```bash
   curl -X POST "http://localhost:8000/api/process-batch" \
     -F "file=@pr_batches/new_pr_batch.csv"
   ```
3. Download the resulting decision file:
   ```bash
   curl -o submission/run_2_decisions_v5.1.csv "http://localhost:8000/api/export-decisions"
   ```
4. Verify the output against the 12 required columns:
   `pr_no, pr_line, resolved_item_code, group_id, po_id, decision, route, supplier_id, unit_price, group_value_inr, suggested_supplier_ids, policy_version, reason`.

---

## Directory Structure

```
├── Dockerfile                     # Multi-stage container build (Node 20 + Python 3.11)
├── docker-compose.yml             # Single-command startup orchestration
├── requirements.txt               # Backend Python dependencies
├── APPROACH.md                    # System architecture, tools used, and blind-test strategy
├── DECISIONS.md                   # Supplier ranking formula weights & edge-case resolutions
├── README.md                      # Setup instructions, architecture, and verification
├── corvo_procurement.db           # SQLite database (policies, audits, overrides)
├── data/                          # Master data and contract files
│   ├── contracts/                 # Contract register, lines, and PDF contracts
│   ├── master_data/               # Items, suppliers, plants, PO history
│   └── pr_batches/                # Test PR batches
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI endpoints and static file serving
│   │   ├── schemas.py             # Pydantic data schemas and input validators
│   │   ├── db.py                  # Database connection and schema migrations
│   │   ├── config.py              # System path configuration and constants
│   │   ├── policy_engine.py       # Policy-as-Data engine, diff generator, and evaluator
│   │   ├── decision_engine.py     # 8-clause decision pipeline and consolidation
│   │   ├── item_matcher.py        # Token-set fuzzy matching for catalog items
│   │   ├── pdf_parser.py          # PyMuPDF contract and amendment extractor
│   │   └── chat_intake.py         # Conversational slot-filling intake assistant
│   └── tests/
│       └── test_worked_examples.py # 17 unit tests verifying worked examples 1-14
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Main view router and navigation
│   │   ├── components/            # UI modular components
│   │   │   ├── Navbar.tsx         # Global navigation and policy version badge
│   │   │   ├── RequesterChat.tsx  # Conversational intake assistant
│   │   │   ├── BuyerWorkspace.tsx # Requirements cockpit with overrides
│   │   │   ├── PolicyManagerView.tsx # Policy diff preview and activation
│   │   │   ├── SuppliersExportView.tsx # Preferred supplier table & export
│   │   │   └── AuditLogView.tsx   # Queryable audit log history
│   │   └── types/                 # TypeScript interfaces
│   ├── package.json               # Frontend dependencies (React, Vite, Lucide)
│   └── vite.config.ts             # Vite configuration with API proxy
└── submission/
    ├── run_1_decisions_v5.0.csv   # Batch 1 decisions under baseline Policy v5.0 (186 rows)
    └── preferred_suppliers_2026-11-01.csv # Top 3 preferred suppliers for all items
```

---

## Documentation References

For exhaustive technical justifications and design records, consult:
- **[APPROACH.md](file:///Users/lucky./VISUAL_PROJECTS/cantill/APPROACH.md)**: System design philosophy, architecture diagrams, LLM agent usage, and blind test execution strategy.
- **[DECISIONS.md](file:///Users/lucky./VISUAL_PROJECTS/cantill/DECISIONS.md)**: Mathematical derivation of the 5-factor ranking formula, tie-breaking heuristics, and unprocessable line handling.

