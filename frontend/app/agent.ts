export type NextAction =
  | "find_suppliers"
  | "check_existing_new_releases"
  | "human_approval"
  | "process_approval"
  | "end";

export interface SupplierOffer {
  supplier_name?: string;
  supplier_id?: number;
  unit_price?: number;
  lead_time_days?: number;
  quality_rating?: number;
  late_deliveries_count?: number;
}

export interface DraftOrderLine {
  product_id?: number;
  product_name?: string;
  quantity?: number;
  unit_price?: number;
}

export interface DraftOrder {
  supplier_id?: number;
  supplier_name?: string;
  items?: DraftOrderLine[];
  total_amount?: number;
  ai_recommendation?: string;
  lead_time_days?: number;
  quality_rating?: number;
}

export interface ReorderProposal {
  product_code?: string;
  product_name?: string;
  current_qty?: number;
  reorder_qty?: number;
  min_threshold?: number;
}

export interface SupplierSelection {
  product_name?: string;
  selected_supplier?: SupplierOffer;
  all_options?: SupplierOffer[];
  ai_recommendation?: string;
}

export interface NewRelease {
  id?: string;
  title?: string;
  artist?: string;
  release_date?: string;
}

export interface CreatedOrder {
  order_id?: number;
  supplier_name?: string;
  total_amount?: number;
}

export interface DecisionHistoryEntry {
  timestamp?: string;
  type?: string;
  supplier_name?: string;
  reason?: string;
  po_id?: number;
  actor?: string;
}

export interface PurchaseOrderProposal {
  product_id?: number;
  product_name?: string;
  quantity?: number;
  status?: string;
  artist?: string;
}

export interface WorkflowData {
  reorder_proposals?: ReorderProposal[];
  supplier_selections?: SupplierSelection[];
  draft_orders?: DraftOrder[];
  created_orders?: CreatedOrder[];
  purchase_order_proposals?: PurchaseOrderProposal[];
  decision_history?: DecisionHistoryEntry[];
}

export interface ProcurementAgentState {
  step?: string;
  status?: string;
  message?: string;
  next_action?: NextAction;
  current_date?: string;
  data?: WorkflowData;
  errors?: string[];

  // Root-level new-release fields coming from nodes
  new_releases?: NewRelease[];
  existing_new_releases?: Record<string, unknown>[];
  new_releases_needing_stock?: Record<string, unknown>[];
  purchase_order_proposals?: PurchaseOrderProposal[];

  // Legacy/derived UI fields
  inventory_alerts?: string[];
  new_release_alerts?: string[];
  supplier_offers?: SupplierOffer[];
  draft_orders?: DraftOrder[];
  approved_orders?: CreatedOrder[];
  rejection_reasons?: string[];
  approval_decision?: "approved" | "rejected" | "pending";
  summary?: string;

  // Path selection for human-in-the-loop
  awaiting_path_selection?: boolean;
  path_choice?: "path_1_suppliers" | "path_2_new_releases" | null;

  // Approval interaction fields
  awaiting_human_approval?: boolean;
  approval_order_indices?: number[];
  rejection_reasons_by_index?: Record<number, string>;
  approved_by?: string;
}

export const INITIAL_AGENT_STATE: ProcurementAgentState = {
  step: "process_due_deliveries",
  status: "pending",
  message: "",
  next_action: "find_suppliers",
  current_date: new Date().toISOString().slice(0, 10),
  data: {
    reorder_proposals: [],
    supplier_selections: [],
    draft_orders: [],
    created_orders: [],
    purchase_order_proposals: [],
    decision_history: [],
  },
  errors: [],
  new_releases: [],
  existing_new_releases: [],
  new_releases_needing_stock: [],
  purchase_order_proposals: [],
  inventory_alerts: [],
  new_release_alerts: [],
  supplier_offers: [],
  draft_orders: [],
  approved_orders: [],
  rejection_reasons: [],
  approval_decision: "pending",
  summary: "",

  // Path selection
  awaiting_path_selection: false,
  path_choice: null,

  // Approval fields
  awaiting_human_approval: false,
  approval_order_indices: [],
  rejection_reasons_by_index: {},
  approved_by: "manager",
};

export function formatCurrency(value?: number): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("nl-NL", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(value);
}
