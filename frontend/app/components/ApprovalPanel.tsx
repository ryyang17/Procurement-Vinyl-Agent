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
  const [localApprovals, setLocalApprovals] = useState<Record<number, boolean>>({});
  const [localRejectionReasons, setLocalRejectionReasons] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const draftOrders = state.draft_orders || [];

  const handleToggleApproval = (index: number) => {
    setLocalApprovals((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));

    if (localApprovals[index]) {
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
    const approvedIndices = Object.entries(localApprovals)
      .filter(([, approved]) => approved)
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

  if (draftOrders.length === 0) {
    return (
      <section className="panel" style={{ backgroundColor: "#f0fff0", borderColor: "#5cb85c", border: "2px solid #5cb85c" }}>
        <h2>Geen Orders Nodig</h2>
        <p style={{ fontSize: "1.1rem", color: "#5cb85c" }}>
          Na de analyse zijn er geen inkooporders nodig. Alles is in orde.
        </p>
        <button
          onClick={() => {
            agent.setState({
              ...state,
              awaiting_human_approval: false,
              approval_order_indices: [],
              rejection_reasons_by_index: {},
              step: "complete",
              status: "ok",
            });
          }}
          style={{
            marginTop: "1rem",
            padding: "0.8rem 1.5rem",
            backgroundColor: "#5cb85c",
            color: "white",
            border: "none",
            borderRadius: "8px",
            cursor: "pointer",
            fontSize: "1rem",
            fontWeight: "bold",
          }}
        >
          Terug naar Dashboard
        </button>
      </section>
    );
  }

  return (
    <section className="panel" style={{ backgroundColor: "#fff8f0", borderColor: "#ff8800", border: "2px solid #ff8800" }}>
      <h2>Goedkeuring Gecombineerde Bestellingen</h2>
      <p>{draftOrders.length} bestellingen (new releases + reorders) wachten op goedkeuring:</p>

      <div style={{ marginTop: "1rem" }}>
        {draftOrders.map((order: ProcurementDraftOrder, idx) => (
          <div
            key={`approval-${idx}`}
            style={{
              marginBottom: "1rem",
              padding: "1rem",
              border: "1px solid #ccc",
              borderRadius: "8px",
              backgroundColor: "white",
              transition: "box-shadow 0.2s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.1)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <input
                type="checkbox"
                checked={localApprovals[idx] ?? false}
                onChange={() => handleToggleApproval(idx)}
                style={{ width: "20px", height: "20px", cursor: "pointer" }}
              />
              <div style={{ flex: 1 }}>
                <strong>{order.supplier_name || `Leverancier ${idx + 1}`}</strong>
                <div style={{ fontSize: "0.9rem", color: "#666" }}>
                  Type: {getOrderType(order)} | Items: {(order.items || []).length}
                </div>
                {order.ai_recommendation && (
                  <div style={{ marginTop: "0.4rem", fontSize: "0.9rem", color: "#344054" }}>
                    Reden voorstel: {order.ai_recommendation}
                  </div>
                )}
                <ul className="list" style={{ marginTop: "0.45rem" }}>
                  {(order.items || []).map((item, itemIdx) => (
                    <li key={`approval-${idx}-item-${itemIdx}`}>
                      {item.product_name || item.product_id || "Onbekend product"} - {item.quantity ?? 0} stuks @ {formatCurrency(item.unit_price)}
                    </li>
                  ))}
                </ul>
              </div>
              <div style={{ textAlign: "right", fontWeight: "bold" }}>
                {formatCurrency(getOrderTotal(order))}
              </div>
            </div>

            {!localApprovals[idx] && (
              <div style={{ marginTop: "0.5rem" }}>
                <label style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.5rem" }}>
                  Reden van afwijzing (optioneel):
                </label>
                <textarea
                  value={localRejectionReasons[idx] ?? ""}
                  onChange={(e) => handleRejectionReasonChange(idx, e.target.value)}
                  placeholder="Voer reden van afwijzing in..."
                  style={{
                    width: "100%",
                    padding: "0.5rem",
                    borderRadius: "4px",
                    border: "1px solid #ccc",
                    fontFamily: "inherit",
                    minHeight: "60px",
                  }}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {submitError && (
        <div style={{ color: "#b42318", marginTop: "0.8rem" }}>
          Fout bij verwerken beslissing: {submitError}
        </div>
      )}

      <button
        onClick={handleSubmitApproval}
        disabled={submitting}
        style={{
          marginTop: "1rem",
          padding: "1rem 2rem",
          backgroundColor: "#ff8800",
          color: "white",
          border: "none",
          borderRadius: "8px",
          cursor: "pointer",
          fontSize: "1rem",
          fontWeight: "bold",
          width: "100%",
          opacity: submitting ? 0.7 : 1,
        }}
      >
        {submitting ? "Verwerken..." : "Goedkeuringen Indienen"}
      </button>
    </section>
  );
}
