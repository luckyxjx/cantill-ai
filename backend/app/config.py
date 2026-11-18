import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))

MASTER_DATA_DIR = DATA_DIR / "master_data"
CONTRACTS_DIR = DATA_DIR / "contracts"
CONTRACTS_PDF_DIR = CONTRACTS_DIR / "pdf"
PR_BATCHES_DIR = DATA_DIR / "pr_batches"
SUBMISSION_DIR = BASE_DIR / "submission"

DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "corvo_procurement.db"))

PLANTS_CSV = MASTER_DATA_DIR / "plants.csv"
ITEM_MASTER_CSV = MASTER_DATA_DIR / "item_master.csv"
SUPPLIER_MASTER_CSV = MASTER_DATA_DIR / "supplier_master.csv"
PO_HISTORY_CSV = MASTER_DATA_DIR / "po_history.csv"

CONTRACT_REGISTER_CSV = CONTRACTS_DIR / "contract_register.csv"
CONTRACT_LINES_CSV = CONTRACTS_DIR / "contract_lines.csv"
SAMPLE_PR_BATCH_CSV = PR_BATCHES_DIR / "sample_pr_batch.csv"

