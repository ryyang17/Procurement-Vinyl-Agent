export type NextAction =
  | "find_suppliers"
  | "check_existing_new_releases"
  | "human_approval"
  | "process_approval"
  | "end";

export interface SupplierOffer {
  supplier_name?: string;
  supplier_id?: string;
  unit_price?: number;
  lead_time_days?: number;
  reliability_score?: number;
  notes?: string;
}

export interface DraftOrderItem {
  product_id?: string;
  product_name?: string;
  quantity?: number;
  unit_price?: number;
  supplier_id?: string;
  supplier_name?: string;
}

export interface SalesVelocityForecast {
  product_id?: number;
  product_name?: string;
  velocity_per_day?: number;
  predicted_stockout_date?: string | null;
  reorder_basis?: string;
  dynamic_reorder_level?: number;
  static_reorder_level?: number;
}

export interface ProcurementAgentState {
  step?: string;
  next_action?: NextAction;
  current_date?: string;
  status?: string;
  inventory_alerts?: string[];
  sales_velocity_alerts?: string[];
  new_release_alerts?: string[];
  supplier_offers?: SupplierOffer[];
  draft_orders?: DraftOrderItem[];
  approved_orders?: DraftOrderItem[];
  rejection_reasons?: string[];
  approval_decision?: "approved" | "rejected" | "pending";
  summary?: string;
  data?: {
    sales_velocity_forecasts?: SalesVelocityForecast[];
    [key: string]: unknown;
  };

  // Path selection for human-in-the-loop
  awaiting_path_selection?: boolean;
  path_choice?: "path_1_suppliers" | "path_2_new_releases" | null;

  // Approval interaction fields
  awaiting_human_approval?: boolean;
  approval_order_indices?: number[];
  rejection_reasons_by_index?: Record<number, string>;
  approved_by?: string;
}

export interface CheckpointDraftOrder {
  supplier_id?: number;
  supplier_name?: string;
  total_amount?: number;
  items?: DraftOrderItem[];
  [key: string]: unknown;
}

export interface PendingCheckpointItem {
  thread_id: string;
  step?: string;
  status?: string;
  message?: string;
  approval_requested_at?: string;
  updated_at?: string;
  draft_orders_count: number;
  draft_orders: CheckpointDraftOrder[];
}

export interface PendingCheckpointResponse {
  items: PendingCheckpointItem[];
  count: number;
}

export interface CheckpointStateResponse {
  thread_id: string;
  state: ProcurementAgentState;
  pending: boolean;
  draft_orders: CheckpointDraftOrder[];
}

export const INITIAL_AGENT_STATE: ProcurementAgentState = {
  step: "process_due_deliveries",
  next_action: "find_suppliers",
  current_date: new Date().toISOString().slice(0, 10),
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
