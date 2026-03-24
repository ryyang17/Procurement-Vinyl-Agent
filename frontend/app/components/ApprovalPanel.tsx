"use client";

import { useState } from "react";
import {
  ProcurementAgentState,
  ProcurementDraftOrder,
  formatCurrency,
} from "../agent";

type DashboardAgent = {
  setState: (state: ProcurementAgentState) => void;
  state?: ProcurementAgentState;
};

type ApprovalPanelProps = {
  state: ProcurementAgentState;
  agent: DashboardAgent;
  onSubmitCheckpointDecision?: (
    approvedIndices: number[],
    rejectionReasonsByIndex: Record<number, string>
  ) => Promise<void>;
};

function getOrderTotal(order: ProcurementDraftOrder): number {
  if (typeof order.total_amount === "number") {
    return order.total_amount;
  }

  return (order.items || []).reduce(
    (acc, item) => acc + (item.quantity ?? 0) * (item.unit_price ?? 0),
    0
  );
}

function getOrderType(order: ProcurementDraftOrder): "New Release" | "Reorder" {
  const source = String(order.source_type || order.order_path || "").toLowerCase();
  if (source.includes("new_release") || source.includes("new_releases")) {
    return "New Release";
  }
  return "Reorder";
}

export default function ApprovalPanel({
  state,
  agent,
  onSubmitCheckpointDecision,
}: ApprovalPanelProps) {
  const [localDecisions, setLocalDecisions] = useState<Record<number, "approved" | "rejected">>({});
  const [localRejectionReasons, setLocalRejectionReasons] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const draftOrders = state.draft_orders || [];

  const handleSetDecision = (index: number, decision: "approved" | "rejected") => {
    setLocalDecisions((prev) => ({
      ...prev,
      [index]: decision,
    }));

    if (decision === "approved") {
      setLocalRejectionReasons((prev) => {
        const nextReasons = { ...prev };
        delete nextReasons[index];
        return nextReasons;
      });
    }
  };

  const handleRejectionReasonChange = (index: number, reason: string) => {
    setLocalRejectionReasons((prev) => ({
      ...prev,
      [index]: reason,
    }));
  };

  const handleSubmitApproval = async () => {
    const approvedIndices = Object.entries(localDecisions)
      .filter(([, decision]) => decision === "approved")
      .map(([idx]) => parseInt(idx, 10));

    try {
      setSubmitting(true);
      setSubmitError(null);

      if (onSubmitCheckpointDecision) {
        await onSubmitCheckpointDecision(approvedIndices, localRejectionReasons);
      } else {
        agent.setState({
          ...state,
          approval_order_indices: approvedIndices,
          rejection_reasons_by_index: localRejectionReasons,
          awaiting_human_approval: false,
          approval_decision: approvedIndices.length > 0 ? "approved" : "rejected",
          next_action: "end",
          approved_by: "manager",
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const totalOrders = draftOrders.length;
  const reviewedOrders = draftOrders.reduce(
    (count, _order, idx) => (localDecisions[idx] ? count + 1 : count),
    0
  );
  const allOrdersReviewed = totalOrders === 0 || reviewedOrders === totalOrders;

  if (draftOrders.length === 0) {
    return (
      <section className="panel panel-checkpoints">
        <details open>
          <summary className="panel-summary">
            <span>Draft Orders - Human Approval</span>
            <span className="summary-chip">Geen draft orders geladen</span>
          </summary>

          <p style={{ marginTop: "0.75rem" }}>
            In deze stap zijn er nog geen draft orders beschikbaar. Eerst moeten producten uit de voorraad-flow
            door `find_suppliers` verwerkt worden om conceptbestellingen op te bouwen.
          </p>

          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
            <button
              className="btn btn-primary"
              onClick={() => {
                agent.setState({
                  ...state,
                  awaiting_human_approval: false,
                  approval_order_indices: [],
                  rejection_reasons_by_index: {},
                  status: "in_progress",
                  step: "find_suppliers",
                  next_action: "find_suppliers",
                });
              }}
            >
              Haal Producten Uit Voorraad
            </button>
          </div>
        </details>
      </section>
    );
  }

  return (
    <section className="panel panel-checkpoints">
      <details open>
        <summary className="panel-summary">
          <span>Draft Orders - Human Approval</span>
          <span className="checkpoint-meta">
            <span className="summary-chip summary-chip-blue">{totalOrders} orders</span>
            <span className="summary-chip">{reviewedOrders}/{totalOrders} beoordeeld</span>
          </span>
        </summary>

        <p style={{ marginTop: "0.75rem", marginBottom: "0.9rem" }}>
          Bekijk elke draft order en kies per order expliciet goedkeuren of afwijzen.
        </p>

        <div style={{ display: "grid", gap: "0.8rem" }}>
          {draftOrders.map((order: ProcurementDraftOrder, idx) => {
            const decision = localDecisions[idx];
            const isApproved = decision === "approved";
            const isRejected = decision === "rejected";

            return (
              <details key={`approval-${idx}`} className="checkpoint-card" open>
                <summary className="checkpoint-summary">
                  <span className="checkpoint-title">{order.supplier_name || `Leverancier ${idx + 1}`}</span>
                  <span className="checkpoint-meta">
                    <span className="summary-chip">{getOrderType(order)}</span>
                    <span className="summary-chip">{(order.items || []).length} items</span>
                    <span className="summary-chip summary-chip-blue">{formatCurrency(getOrderTotal(order))}</span>
                    {isApproved && <span className="summary-chip summary-chip-green">Goedgekeurd</span>}
                    {isRejected && <span className="summary-chip">Afgewezen</span>}
                    {!decision && <span className="summary-chip">Nog geen keuze</span>}
                  </span>
                </summary>

                <div className="checkpoint-body" style={{ display: "grid", gap: "0.7rem" }}>
                  {order.ai_recommendation && (
                    <div style={{ color: "#344054", fontSize: "0.92rem" }}>
                      Reden voorstel: {order.ai_recommendation}
                    </div>
                  )}

                  <ul className="list">
                    {(order.items || []).length === 0 && <li>Geen items</li>}
                    {(order.items || []).map((item, itemIdx) => (
                      <li key={`approval-${idx}-item-${itemIdx}`}>
                        {item.product_name || item.product_id || "Onbekend product"} - {item.quantity ?? 0} stuks @ {formatCurrency(item.unit_price)}
                      </li>
                    ))}
                  </ul>

                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-success"
                      disabled={submitting}
                      onClick={() => handleSetDecision(idx, "approved")}
                    >
                      Goedkeuren
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      disabled={submitting}
                      onClick={() => handleSetDecision(idx, "rejected")}
                    >
                      Afwijzen
                    </button>
                  </div>

                  {isRejected && (
                    <div>
                      <label style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.35rem" }}>
                        Reden van afwijzing (optioneel)
                      </label>
                      <textarea
                        value={localRejectionReasons[idx] ?? ""}
                        onChange={(e) => handleRejectionReasonChange(idx, e.target.value)}
                        placeholder="Voer reden van afwijzing in..."
                        disabled={submitting}
                        style={{ width: "100%", minHeight: "70px" }}
                      />
                    </div>
                  )}
                </div>
              </details>
            );
          })}
        </div>

        {submitError && (
          <div style={{ color: "#b42318", marginTop: "0.8rem" }}>
            Fout bij verwerken beslissing: {submitError}
          </div>
        )}

        <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", alignItems: "center", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmitApproval}
            disabled={submitting || !allOrdersReviewed}
          >
            {submitting ? "Verwerken..." : "Beslissing Afronden"}
          </button>

          {!allOrdersReviewed && (
            <span style={{ color: "#b42318", fontSize: "0.9rem" }}>
              Maak eerst voor alle draft orders een keuze.
            </span>
          )}
        </div>
      </details>
    </section>
  );
}
