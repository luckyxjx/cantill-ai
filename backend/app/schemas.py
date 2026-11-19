import re
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
import math

# PR Batch Row Input
class PRLineInput(BaseModel):
    pr_no: str
    pr_line: int
    created_at: str
    requester: str
    department: str
    plant: str
    item_code: Optional[str] = None
    description: str
    quantity: int
    uom: str
    estimated_unit_price: Optional[float] = None
    need_by_date: str
    urgency: str = "Normal"

    @field_validator("plant", mode="before")
    @classmethod
    def clean_plant(cls, v):
        return str(v).strip().upper() if v is not None else ""

    @field_validator("quantity", mode="before")
    @classmethod
    def clean_quantity(cls, v):
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return int(round(v))
        s = str(v).replace(",", "").strip()
        try:
            return int(round(float(s)))
        except (ValueError, TypeError):
            return 0

    @field_validator("item_code", mode="before")
    @classmethod
    def clean_item_code(cls, v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        s = str(v).strip()
        return s.upper() if s and s.lower() != "nan" else None

    @field_validator("estimated_unit_price", mode="before")
    @classmethod
    def clean_est_price(cls, v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        if isinstance(v, str):
            v_str = re.sub(r'[₹$Rs,]', '', v).strip()
            if not v_str or v_str.lower() == "nan":
                return None
            try:
                return float(v_str)
            except (ValueError, TypeError):
                return None
        return float(v)


# 12-Column Required Output Row
class PRDecisionOutput(BaseModel):
    pr_no: str
    pr_line: int
    resolved_item_code: str
    group_id: str
    po_id: str = ""
    decision: str  # "PO" or "SOURCING_REQUEST"
    route: str     # "CONTRACT_PO", "EMERGENCY_PO", "SPOT_PO", "RFQ", "RFP", "CAPEX_SOURCING", "NEW_ITEM_SOURCING", "NOT_PROCESSED"
    supplier_id: str = ""
    unit_price: Optional[float] = None
    group_value_inr: float
    suggested_supplier_ids: str = ""
    policy_version: str = "v5.0"
    reason: str

# Buyer Workspace Requirement representation
class BuyerRequirementView(BaseModel):
    group_id: str
    item_code: str
    item_description: str
    category: str
    item_type: str
    plant: str
    total_quantity: int
    uom: str
    first_created_at: str
    first_need_by_date: str
    is_emergency: bool
    group_value_inr: float
    unit_price: Optional[float]
    decision: str
    route: str
    po_id: str = ""
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    suggested_suppliers: List[Dict[str, Any]] = []
    policy_version: str
    reason: str
    status: str = "PENDING"  # PENDING, APPROVED, OVERRIDDEN
    override_reason: Optional[str] = None
    action_by: Optional[str] = None
    action_at: Optional[str] = None
    pr_lines: List[Dict[str, Any]] = []

# Preferred Supplier Export Row
class PreferredSupplierRow(BaseModel):
    item_code: str
    rank: int
    supplier_id: str
    supplier_name: str
    reference_price: Optional[float]
    score: float
    recency: float
    po_count: int
    has_contract: bool
    on_time_pct: int
    quality_rating: float

# Policy-as-Data Definition Models
class PolicyCondition(BaseModel):
    field: Optional[str] = None
    op: Optional[str] = None
    value: Optional[Any] = None
    and_: Optional[List["PolicyCondition"]] = Field(None, alias="and")
    or_: Optional[List["PolicyCondition"]] = Field(None, alias="or")

PolicyCondition.model_rebuild()

class PolicyRule(BaseModel):
    id: str
    name: str
    condition: Dict[str, Any]
    route: str
    decision: str
    suggest_count: Optional[int] = 0
    supplier_selection: Optional[str] = None  # "contract_supplier", "1st_preferred", "none"
    price_selection: Optional[str] = None     # "contract_rate", "reference_price", "none"
    require_approval: Optional[bool] = False
    reason_template: str

class PolicyParameters(BaseModel):
    anti_splitting_window_days: int = 14
    need_by_window_days: int = 7
    po_consolidation_window_hours: int = 24
    preferred_supplier_history_days: int = 548
    price_history_days: int = 365
    ranking_weights: Dict[str, float] = {
        "recency": 0.25,
        "po_count": 0.20,
        "contract": 0.15,
        "on_time": 0.20,
        "quality": 0.20
    }
    category_ranking_weights: Dict[str, float] = {
        "on_time": 0.50,
        "quality": 0.50
    }

class PolicySchema(BaseModel):
    version: str
    title: str
    document_ref: str = "CORVO-PROC-POL-04"
    effective_date: str
    active: bool = False
    parameters: PolicyParameters = PolicyParameters()
    rules: List[PolicyRule]

# Policy Amendment Ingestion & Diff
class PolicyDiff(BaseModel):
    summary: str
    changes: List[str]
    old_version: str
    new_version: str
    effective_date: str
    proposed_policy: Dict[str, Any]

# Chat Intake Slot State
class ChatPRState(BaseModel):
    item_code: Optional[str] = None
    matched_description: Optional[str] = None
    raw_query: str
    quantity: Optional[int] = None
    uom: Optional[str] = None
    plant: Optional[str] = None
    need_by_date: Optional[str] = None
    urgency: str = "Normal"
    estimated_unit_price: Optional[float] = None
    missing_fields: List[str] = []
    is_ready_to_create: bool = False
    confirmed: bool = False
    created_pr_no: Optional[str] = None
