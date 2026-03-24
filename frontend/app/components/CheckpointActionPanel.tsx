"use client";

import { useState } from "react";
import {
  PendingCheckpointItem,
  formatCurrency,
} from "../agent";

type CheckpointActionPanelProps = {
  checkpoint: PendingCheckpointItem;
  onSubmitDecision: (
    approvedIndices: number[],
    rejectionReasonsByIndex: Record<number, string>
  ) => Promise<void>;
  isLoading?: boolean;
};

export default function CheckpointActionPanel({
  checkpoint,
  onSubmitDecision,
  isLoading = false,
}: CheckpointActionPanelProps) {
  const [localApprovals, setLocalApprovals] = useState<Record<number, boolean>>({});
  const [localRejectionReasons, setLocalRejectionReasons] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const draftOrders = checkpoint.draft_orders || [];

  // Bepaal checkpoint type op basis van step/status
  const isApprovalCheckpoint =
    checkpoint.step === "awaiting_human_input" || 
    checkpoint.status === "awaiting_approval" ||
    checkpoint.message?.toLowerCase().includes("bestellingen");
  
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

  const handleSubmit = async () => {
    try {
      setSubmitting(true);
      setSubmitError(null);

      const approvedIndices = Object.entries(localApprovals)
        .filter(([, approved]) => approved)
        .map(([idx]) => parseInt(idx, 10));

      await onSubmitDecision(approvedIndices, localRejectionReasons);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setSubmitError(message);
    } finally {
      setSubmitting(false);
    }
  };

  // Approval Checkpoint: toont per-product accepteren/afwijzen UI
  if (isApprovalCheckpoint) {
    return (
      <form
        onSubmit={e => {
          e.preventDefault();
          handleSubmit();
        }}
        style={{
          border: "1px solid #ff8800",
          borderRadius: "8px",
          padding: "1rem",
          backgroundColor: "#fff8f0",
          marginTop: "0.8rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.8rem"
        }}
      >
        <h4 style={{ marginTop: 0, marginBottom: "0.8rem", color: "#b30000" }}>
          Goedkeuring Vereist
        </h4>

        {submitError && (
          <div style={{ color: "#b42318", marginBottom: "0.8rem", fontSize: "0.9rem" }}>
            Fout: {submitError}
          </div>
        )}

        {draftOrders.length === 0 ? (
          <p>Geen bestellingen in deze checkpoint.</p>
        ) : (
          <div style={{ display: "grid", gap: "0.8rem", marginBottom: "1rem" }}>
            {draftOrders.map((order, idx) => {
              const isApproved = localApprovals[idx] || false;
              const hasRejectionReason = Boolean(localRejectionReasons[idx]);
              return (
                <div
                  key={`checkpoint-order-${idx}`}
                  style={{
                    border: `2px solid ${isApproved ? "#5cb85c" : hasRejectionReason ? "#b42318" : "#e4e7ec"}`,
                    borderRadius: "8px",
                    padding: "0.8rem",
                    backgroundColor: isApproved ? "#f0fff0" : hasRejectionReason ? "#fff0f0" : "#fcfcfd",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.8rem", marginBottom: "0.6rem" }}>
                    <input
                      type="checkbox"
                      checked={isApproved}
                      onChange={() => handleToggleApproval(idx)}
                      disabled={submitting || isLoading}
                      style={{ cursor: "pointer", width: "18px", height: "18px" }}
                    />
                    <div style={{ flex: 1 }}>
                      <strong>{order.supplier_name || `Leverancier ${idx + 1}`}</strong>
                      {typeof order.total_amount === "number" && (
                        <span style={{ marginLeft: "1rem", color: "#666" }}>
                          Totaal: {formatCurrency(order.total_amount)}
                        </span>
                      )}
                    </div>
                    <span
                      style={{
                        fontSize: "0.85rem",
                        padding: "0.3rem 0.6rem",
                        borderRadius: "4px",
                        backgroundColor: isApproved ? "#5cb85c" : hasRejectionReason ? "#b42318" : "#e4e7ec",
                        color: isApproved || hasRejectionReason ? "white" : "#333",
                      }}
                    >
                      {isApproved ? "✓ Goedgekeurd" : hasRejectionReason ? "✗ Afgewezen" : "⊗ Geen keuze"}
                    </span>
                  </div>
                  {Array.isArray(order.items) && (order.items as Array<{ product_name?: string; product_id?: string; quantity?: number; unit_price?: number }>).length > 0 && (
                    <ul style={{ marginBottom: "0.6rem", marginLeft: "2rem", fontSize: "0.9rem", margin: 0 }}>
                      {(order.items as Array<{ product_name?: string; product_id?: string; quantity?: number; unit_price?: number }>).map((item, itemIdx) => (
                        <li key={`checkpoint-order-${idx}-item-${itemIdx}`}>
                          {item.product_name || item.product_id || "Onbekend product"} — {item.quantity ?? 0} stuks @{" "}
                          {formatCurrency(item.unit_price ?? 0)}
                        </li>
                      ))}
                    </ul>
                  )}
                  {order.ai_recommendation && (
                    <div style={{ marginBottom: "0.6rem", color: "#344054", fontSize: "0.9rem", marginLeft: "2rem" }}>
                      <strong>Voorstel reden:</strong> {String(order.ai_recommendation)}
                    </div>
                  )}
                  {!isApproved && (
                    <textarea
                      placeholder="Optioneel: Reden voor afwijzing..."
                      value={localRejectionReasons[idx] || ""}
                      onChange={(e) => handleRejectionReasonChange(idx, e.target.value)}
                      disabled={submitting || isLoading}
                      style={{
                        width: "100%",
                        marginLeft: 0,
                        padding: "0.6rem",
                        fontSize: "0.9rem",
                        borderRadius: "4px",
                        border: "1px solid #ccc",
                        fontFamily: "monospace",
                        resize: "vertical",
                        minHeight: "60px",
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
        <button
          type="submit"
          disabled={submitting || isLoading}
          style={{
            padding: "0.8rem 1.5rem",
            backgroundColor: "#ff8800",
            color: "white",
            border: "none",
            borderRadius: "6px",
            fontWeight: "bold",
            cursor: submitting || isLoading ? "not-allowed" : "pointer",
            opacity: submitting || isLoading ? 0.6 : 1,
          }}
        >
          {submitting
            ? "Verwerken..."
            : draftOrders.length === 0
              ? "Verwijder deze checkpoint"
              : "📋 Plaatsen Bestelling"}
        </button>
      </form>
    );
  }

  // Proposal Checkpoint: toont alleen een "Verder gaan" knop
  return (
    <div
      style={{
        border: "1px solid #027a48",
        borderRadius: "8px",
        padding: "1rem",
        backgroundColor: "#f0fff0",
        marginTop: "0.8rem",
      }}
    >
      <h4 style={{ marginTop: 0, marginBottom: "0.8rem", color: "#027a48" }}>
        Voorstel
      </h4>

      <p style={{ marginBottom: "1rem", fontSize: "0.95rem", color: "#344054" }}>
        {checkpoint.message || "Voorstel gereed voor verwerking."}
      </p>

      {(draftOrders || []).length > 0 && (
        <div style={{ marginBottom: "1rem", maxHeight: "200px", overflowY: "auto" }}>
          {(draftOrders || []).map((order, idx) => (
            <div key={`proposal-order-${idx}`} style={{ fontSize: "0.9rem", marginBottom: "0.5rem", color: "#555" }}>
              <strong>{order.supplier_name || `Voorstel ${idx + 1}`}</strong> — {"{"}
              {String(order.ai_recommendation || "Geen reden")}
              {"}"}
            </div>
          ))}
        </div>
      )}

      {submitError && (
        <div style={{ color: "#b42318", marginBottom: "0.8rem", fontSize: "0.9rem" }}>
          Fout: {submitError}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={submitting || isLoading}
        style={{
          padding: "0.8rem 1.5rem",
          backgroundColor: "#027a48",
          color: "white",
          border: "none",
          borderRadius: "6px",
          fontWeight: "bold",
          cursor: submitting || isLoading ? "not-allowed" : "pointer",
          opacity: submitting || isLoading ? 0.6 : 1,
        }}
      >
        {submitting ? "Verwerken..." : "✓ Verder Gaan"}
      </button>
    </div>
  );
}
