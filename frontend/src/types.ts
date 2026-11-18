export interface PRLine {
  pr_no: string;
  pr_line: number;
  created_at: string;
  requester: string;
  department: string;
  plant: string;
  item_code?: string;
  description: string;
  quantity: number;
  uom: string;
  estimated_unit_price?: number;
  need_by_date: string;
  urgency: string;
}

export interface PRDecision {
  pr_no: string;
  pr_line: number;
  resolved_item_code: string;
  group_id: string;
  po_id: string;
  decision: string;
  route: string;
  supplier_id: string;
  unit_price?: number;
  group_value_inr: number;
  suggested_supplier_ids: string;
  policy_version: string;
  reason: string;
}

export interface BuyerRequirement {
  group_id: string;
  item_code: string;
  item_description: string;
  category: string;
  item_type: string;
  plant: string;
  total_quantity: number;
  uom: string;
  first_created_at: string;
  first_need_by_date: string;
  is_emergency: boolean;
  group_value_inr: number;
  unit_price?: number;
  decision: string;
  route: string;
  po_id: string;
  supplier_id?: string;
  supplier_name?: string;
  suggested_suppliers: Array<{ supplier_id: string; name: string }>;
  policy_version: string;
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'OVERRIDDEN';
  override_reason?: string;
  action_by?: string;
  action_at?: string;
  pr_lines: PRLine[];
}

export interface PreferredSupplier {
  item_code: string;
  rank: number;
  supplier_id: string;
  supplier_name: string;
  reference_price?: number;
  score: number;
  recency: number;
  po_count: number;
  has_contract: boolean;
  on_time_pct: number;
  quality_rating: number;
}

export interface PolicyRule {
  id: string;
  name: string;
  condition: Record<string, any>;
  route: string;
  decision: string;
  suggest_count?: number;
  supplier_selection?: string;
  price_selection?: string;
  reason_template: string;
}

export interface PolicyData {
  version: string;
  title: string;
  document_ref: string;
  effective_date: string;
  active: boolean;
  parameters: {
    anti_splitting_window_days: number;
    need_by_window_days: number;
    po_consolidation_window_hours: number;
    spot_po_limit: number;
    emergency_po_limit: number;
    rfq_limit: number;
    ranking_weights: Record<string, number>;
  };
  rules: PolicyRule[];
}

export interface AuditLog {
  id: number;
  timestamp: string;
  user_id: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, any>;
}

