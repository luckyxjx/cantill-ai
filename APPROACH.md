# PR-to-PO Procurement Copilot — Engineering Approach & Architecture (`APPROACH.md`)

## 1. System Philosophy & Objectives
The **PR-to-PO Procurement Copilot** was designed for **Corvo Engineering** to transition procurement from slow, manual, error-prone processes to a policy-governed, autonomous system. The architecture fulfills three critical business imperatives:
1. **Zero-Code Policy Adaptability (Policy-as-Data)**: Future amendments—such as shifting spot PO limits, category approval gates, or plant-specific thresholds—must take effect dynamically without code changes, recompilation, or redeployment.
2. **Absolute Determinism & Mathematical Accuracy**: Every procurement rule (anti-splitting windows, contract ceiling consumption, preferred supplier scoring) must produce 100% reproducible results verified against official worked examples.
3. **Buyer Empowerment & Compliance**: Requester chat streamlines intake while the Buyer Workspace provides full clause visibility, audit logging, and transparent override capabilities.

---

## 2. Tools & AI Systems Used
In compliance with Section 7 of the task brief:
- **AI Coding Assistants**: Utilized modern LLM capabilities (DeepMind Gemini models in Antigravity IDE) for rapid prototyping, mathematical parameter space exploration, test generation, and frontend UI scaffolding.
- **Python Data Ecosystem**: `pandas` and `numpy` for data manipulation, `rapidfuzz` for high-throughput string matching, `PyMuPDF` (`fitz`) for PDF contract and amendment extraction.
- **Web Stack**: `FastAPI` (Python 3.11) asynchronous backend paired with `Vite + React 18 + TypeScript + Tailwind CSS` for the frontend.
- **Storage**: Relational SQLite database for versioned policy schemas, audit trails, and requirement overrides.

---

## 3. High-Level Architecture & Separation of Concerns

```
                  ┌──────────────────────────────────────────────┐
                  │           React Frontend (Vite)              │
                  │  • Requester Chat  • Buyer Workspace         │
                  │  • Policy Manager  • Supplier Explorer       │
                  └──────────────────────┬───────────────────────┘
                                         │ REST API
                  ┌──────────────────────▼───────────────────────┐
                  │            FastAPI Backend                   │
                  │  /api/process-batch  /api/policy/*           │
                  │  /api/chat/message   /api/suppliers/*        │
                  └──────────┬───────────────────────┬───────────┘
                             │                       │
      ┌──────────────────────▼───────┐   ┌───────────▼──────────────────┐
      │     Item Matcher Engine      │   │     Policy-as-Data Engine    │
      │  • Token Normalization       │   │  • Versioned JSON Schema     │
      │  • Levenshtein & Token Ratio │   │  • AST Condition Evaluator   │
      │  • Alias Expansion           │   │  • Natural Language Diff Gen │
      └──────────────────────┬───────┘   └───────────┬──────────────────┘
                             │                       │
                  ┌──────────▼───────────────────────▼───────────┐
                  │              Decision Engine                 │
                  │  1. Identification  2. Clubbing (Anti-Split) │
                  │  3. Valuation       4. Contract Ceilings     │
                  │  5. Decision Rules  6. Supplier Ranking      │
                  │  7. PO Consolidation                         │
                  └──────────────────────┬───────────────────────┘
                                         │
                  ┌──────────────────────▼───────────────────────┐
                  │      Database & Storage (SQLite / Data)      │
                  │  • Policies  • Contracts  • Audit Logs       │
                  └──────────────────────────────────────────────┘
```

### 3.1 Policy-as-Data Architecture
The core innovation is that **no policy rules or financial limits are hardcoded in application logic**.
- Policies are stored as structured JSON records in the `policies` table.
- Each policy version (e.g. `v5.0`, `v5.1`) specifies:
  - `parameters`: Windows (14-day clubbing, 7-day need-by, 24-hour PO consolidation), scoring weights, and threshold defaults.
  - `rules`: An ordered array of rule objects, each featuring an abstract syntax tree condition (`and`, `or`, `==`, `<=`, `in`), an execution route, a decision outcome, and dynamic reason templates.
- **Runtime Dynamic Loading**: The Decision Engine evaluates the active policy for each batch run.
- **Amendment Ingestion & Diff Preview**: When an amendment document (PDF/text) is provided, `PolicyManager.parse_amendment_text` extracts threshold changes or plant-specific overrides, creates a new version (`v5.1`), and generates plain-language diffs for buyer approval.

### 3.2 Decision Engine Separation
The decision engine (`backend/app/decision_engine.py`) is completely decoupled from HTTP handlers and UI components:
- Receives typed `List[PRLineInput]` and an optional `PolicyData` schema.
- Executes the 8 policy clauses in strict sequence.
- Returns immutable `List[PRDecisionOutput]` rows matching the required 12 columns.
- Fully unit-testable in isolation via `test_worked_examples.py`.

### 3.3 Free-Text Item Resolution
Requesters frequently use informal descriptions (e.g. *"brg 6308 ZZ for maintenance"* or *"pneu cylinder 50x100"*).
- Preprocesses queries by stripping noise words (*urgent*, *as per sample*, *repeat*, *for maintenance*).
- Expands domain abbreviations (*brg* $\rightarrow$ *bearing*, *pneu* $\rightarrow$ *pneumatic*, *hyd* $\rightarrow$ *hydraulic*).
- Combines token intersection with `token_set_ratio` similarity.
- Bounded by a strict $0.55$ confidence threshold: valid items resolve with $>0.80$ confidence, while unknown items (*Drinking water purifier 50 LPH*, *Ultrasonic thickness gauge*) cleanly classify as `NEW` without false matches.

### 3.4 Contract PDF Extraction
Contracts signed after the monthly register update (e.g. `RC-2026-031` and `RC-2026-033`) exist only as signed PDFs in `contracts/pdf/`.
- `pdf_parser.py` uses PyMuPDF (`fitz`) to extract header metadata, value cap, validity dates, and tabular schedule rates automatically upon startup or user upload.

---

## 4. Blind Test Execution Flow (Run 1 & Run 2 Strategy)

```
                       BLIND TEST WORKFLOW
                       
   [New PR Batch CSV] ────────► Run 1 (Under Policy v5.0) ────────► export Run 1 CSV
                                                                    (submission/run_1_decisions_v5.0.csv)
                                         │
                                         ▼
   [Amendment Document] ──────► Upload in Policy UI ─────────────► Plain-Language Diff Preview
                                         │
                                         ▼
                               Click "Approve & Activate"
                                         │
                                         ▼
                               New Version (v5.1) Activated
                                         │
                                         ▼
   [Same PR Batch CSV] ───────► Run 2 (Under Policy v5.1) ────────► export Run 2 CSV
                                                                    (submission/run_2_decisions_v5.1.csv)
                                         │
                                         ▼
   [Target Date] ─────────────► Export Preferred Suppliers ───────► export Supplier CSV
                                                                    (submission/preferred_suppliers_YYYY-MM-DD.csv)
```

1. **Run 1**: Upload the evaluation PR batch CSV via the UI or `POST /api/process-batch`. Export decisions to `submission/run_1_decisions_v5.0.csv`.
2. **Run 2 (Policy Update)**:
   - Go to the **Policy Engine** tab in the web application.
   - Upload the provided amendment document (PDF, Markdown, or plain text) or paste its text.
   - Review the automatic side-by-side diff preview.
   - Click **Approve & Activate New Policy Version**.
   - Re-process the same PR batch CSV. The engine applies the new thresholds and plant-specific rules immediately.
   - Export decisions to `submission/run_2_decisions_v5.1.csv`.
3. **Preferred Supplier Export**:
   - Go to the **Suppliers & Exports** tab.
   - Enter the target date.
   - Click **Export Preferred Suppliers CSV (Top 3)** to generate the CSV.

