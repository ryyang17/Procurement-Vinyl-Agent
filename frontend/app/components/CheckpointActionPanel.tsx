"use client";

import { useState } from "react";
import {
  PendingCheckpointItem,
  ProcurementAgentState,
  ProcurementDraftOrder,
  formatCurrency,
} from "../agent";

type CheckpointActionPanelProps = {
  checkpoint?: PendingCheckpointItem;
  state?: ProcurementAgentState;
  agent?: {
    setState: (state: ProcurementAgentState) => void;
    state?: ProcurementAgentState;
  };
  onSubmitDecision?: (
    approvedIndices: number[],
    rejectionReasonsByIndex: Record<number, string>
  ) => Promise<void>;
  isLoading?: boolean;
};

export default function CheckpointActionPanel({
  checkpoint,
  state,
  agent,
  onSubmitDecision,
  isLoading = false,
}: CheckpointActionPanelProps) {
  const NEW_RELEASE_WINDOW_DAYS = 5;

  const parseDate = (raw?: string): Date | null => {
    if (!raw) return null;
    const parsed = new Date(raw);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const isRecentRelease = (order: ProcurementDraftOrder): boolean => {
    const cutoff = new Date(Date.now() - NEW_RELEASE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
    const firstItem = Array.isArray(order.items) ? order.items[0] : undefined;

    const releaseDate = parseDate(order.release_date || firstItem?.release_date);
    const createdAt = parseDate(order.created_at || firstItem?.created_at);

    if (releaseDate && releaseDate >= cutoff) return true;
    if (createdAt && createdAt >= cutoff) return true;
    return false;
  };
  const toOrderTypeSource = (order: ProcurementDraftOrder): string => {
    const directSource = String(order.source_type || order.order_path || "").toLowerCase();
    if (directSource) return directSource;

    const firstItem = Array.isArray(order.items) ? order.items[0] : undefined;
    return String(firstItem?.source_type || firstItem?.order_path || "").toLowerCase();
  };

  const normalizeDraftOrders = (): ProcurementDraftOrder[] => {
    if (checkpoint) {
      return Array.isArray(checkpoint.draft_orders)
        ? (checkpoint.draft_orders as ProcurementDraftOrder[])
        : [];
    }

    const directDraftOrders = Array.isArray(state?.draft_orders)
      ? (state?.draft_orders as ProcurementDraftOrder[])
      : [];
    const nestedDraftOrders = Array.isArray(state?.data?.draft_orders)
      ? (state?.data?.draft_orders as ProcurementDraftOrder[])
      : [];

    const mergedDraftOrders = [
      ...directDraftOrders,
      ...nestedDraftOrders,
    ];

    if (mergedDraftOrders.length > 0) {
      return mergedDraftOrders;
    }

    const directProposals = Array.isArray(state?.purchase_order_proposals)
      ? state.purchase_order_proposals
      : [];
    const nestedProposals = Array.isArray(state?.data?.purchase_order_proposals)
      ? state.data.purchase_order_proposals
      : [];
    const proposals = [...directProposals, ...nestedProposals] as Array<{
      product_id?: string;
      product_name?: string;
      quantity?: number;
      market_popularity_score?: number;
    }>;

    return proposals.map((proposal) => ({
      supplier_id: 1,
      supplier_name: "Spotify Market Suggestion",
      source_type: "new_releases",
      order_path: "new_releases",
      total_amount: 0,
      market_popularity_score: proposal.market_popularity_score,
      ai_recommendation: "Inkoop gebaseerd op nieuwe release detectie.",
      items: [{
        product_id: proposal.product_id,
        product_name: proposal.product_name,
        quantity: proposal.quantity,
        unit_price: 0,
        source_type: "new_releases",
        order_path: "new_releases",
      }],
    }));
  };

  const [localApprovals, setLocalApprovals] = useState<Record<number, boolean>>({});
  const [localRejectionReasons, setLocalRejectionReasons] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const draftOrders = normalizeDraftOrders();

  const parseAiRecommendation = (raw: unknown): { supplier?: string; reason: string } | null => {
    if (!raw) return null;
    
    const text = String(raw);
    const supplierMatch = text.match(/LEVERANCIER\s*:\s*([^\n]+)/i);
    const reasonMatch = text.match(/REDEN\s*:\s*([\s\S]*)/i);

    const supplier = supplierMatch?.[1]?.trim();
    const reason = (reasonMatch?.[1] || text).trim();

    if (!reason) return null;
    return { supplier, reason };
  };

  const getOrderType = (order: ProcurementDraftOrder): "New Release" | "Reorder" => {
    const source = toOrderTypeSource(order);
    const recommendation = String(order.ai_recommendation || "").toLowerCase();
    const supplierName = String(order.supplier_name || "").toLowerCase();

    if (
      source.includes("new_release") ||
      source.includes("new_releases") ||
      supplierName.includes("spotify market suggestion") ||
      recommendation.includes("nieuwe release") ||
      recommendation.includes("spotify") ||
      typeof order.market_popularity_score === "number" ||
      isRecentRelease(order)
    ) {
      return "New Release";
    }
    return "Reorder";
  };

  const getOrderSourceLabel = (order: ProcurementDraftOrder): string => {
    const orderType = getOrderType(order);
    if (orderType === "New Release") {
      return "Bron: Spotify/Markttrend";
    }
    return "Bron: Lage voorraad";
  };

  // Bepaal checkpoint type op basis van step/status
  const isApprovalCheckpoint =
    (checkpoint?.step === "awaiting_human_input" || 
    checkpoint?.status === "awaiting_approval" ||
    checkpoint?.message?.toLowerCase().includes("bestellingen")) ||
    (state?.awaiting_human_approval === true || 
    state?.step === "human_approval" ||
    state?.step === "create_purchase_order" ||
    state?.status === "awaiting_approval" ||
    state?.status === "awaiting_human_approval");
  
  const handleToggleApproval = (index: number) => {
    setLocalApprovals((prev) => {
      const nextApproved = !prev[index];

      if (nextApproved) {
        setLocalRejectionReasons((prevReasons) => {
          const nextReasons = { ...prevReasons };
          delete nextReasons[index];
          return nextReasons;
        });
      }

      return {
        ...prev,
        [index]: nextApproved,
      };
    });
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

      if (onSubmitDecision) {
        await onSubmitDecision(approvedIndices, localRejectionReasons);
      } else if (agent && state) {
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

  const allOrdersHaveDecision =
    draftOrders.length > 0 &&
    draftOrders.every((_order, idx) => {
      const isApproved = Boolean(localApprovals[idx]);
      const hasRejectionReason = Boolean((localRejectionReasons[idx] || "").trim());
      return isApproved || hasRejectionReason;
    });

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
          {draftOrders.length > 0 && draftOrders.every(o => getOrderType(o) === "New Release") && (
            <span style={{ fontSize: "0.75rem", marginLeft: "0.5rem", backgroundColor: "#fef3c7", padding: "0.2rem 0.6rem", borderRadius: "3px" }}>
              🎵 Nieuwe Releases
            </span>
          )}
        </h4>

        {submitError && (
          <div style={{ color: "#b42318", marginBottom: "0.8rem", fontSize: "0.9rem" }}>
            Fout: {submitError}
          </div>
        )}

        {draftOrders.length === 0 ? (
          <p>Geen bestellingen beschikbaar.</p>
        ) : (
          <div style={{ display: "grid", gap: "0.8rem", marginBottom: "1rem" }}>
            {draftOrders.map((order, idx) => {
              const isApproved = localApprovals[idx] || false;
              const hasRejectionReason = Boolean(localRejectionReasons[idx]);
              const recommendation = parseAiRecommendation(order.ai_recommendation);
              const displaySupplier = recommendation?.supplier || order.supplier_name || `Leverancier ${idx + 1}`;
              const orderType = getOrderType(order);
              const orderSourceLabel = getOrderSourceLabel(order);
              const totalAmount = typeof order.total_amount === "number" ? order.total_amount : 0;

              return (
                <div
                  key={`checkpoint-order-${idx}`}
                  style={{
                    border: `2px solid ${isApproved ? "#5cb85c" : hasRejectionReason ? "#b42318" : "#e4e7ec"}`,
                    borderRadius: "8px",
                    padding: "0.8rem",
                    backgroundColor: isApproved ? "#f0fff0" : hasRejectionReason ? "#fff0f0" : "#fcfcfd",
                    width: "100%",
                    boxSizing: "border-box",
                    overflow: "hidden",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "0.8rem", marginBottom: "0.6rem" }}>
                    <input
                      type="checkbox"
                      checked={isApproved}
                      onChange={() => handleToggleApproval(idx)}
                      disabled={submitting || isLoading}
                      style={{ cursor: "pointer", width: "18px", height: "18px", flexShrink: 0, marginTop: "2px" }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <strong>{displaySupplier}</strong>
                      <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginTop: "0.3rem", fontSize: "0.85rem" }}>
                        <span style={{ backgroundColor: orderType === "New Release" ? "#fef3c7" : "#e0e7ff", padding: "0.2rem 0.5rem", borderRadius: "3px", fontWeight: 700 }}>
                          {orderType}
                        </span>
                        <span style={{ backgroundColor: "#f3f4f6", padding: "0.2rem 0.5rem", borderRadius: "3px" }}>
                          {orderSourceLabel}
                        </span>
                        <span style={{ backgroundColor: "#f3f4f6", padding: "0.2rem 0.5rem", borderRadius: "3px" }}>
                          {(order.items || []).length} items
                        </span>
                        <span style={{ backgroundColor: "#dbeafe", padding: "0.2rem 0.5rem", borderRadius: "3px" }}>
                          {formatCurrency(totalAmount)}
                        </span>
                      </div>
                    </div>
                    <span
                      style={{
                        fontSize: "0.85rem",
                        padding: "0.3rem 0.6rem",
                        borderRadius: "4px",
                        backgroundColor: isApproved ? "#5cb85c" : hasRejectionReason ? "#b42318" : "#e4e7ec",
                        color: isApproved || hasRejectionReason ? "white" : "#333",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {isApproved ? "✓ Goed" : hasRejectionReason ? "✗ Afg" : "⊗ Geen"}
                    </span>
                  </div>

                  {order.ai_recommendation && (
                    <div
                      style={{
                        marginBottom: "0.6rem",
                        marginLeft: "2rem",
                        border: "1px solid #d0d5dd",
                        borderRadius: "6px",
                        padding: "0.6rem",
                        backgroundColor: "#f8fafc",
                        color: "#344054",
                        fontSize: "0.9rem",
                      }}
                    >
                      <strong>Reden voorstel:</strong> {order.ai_recommendation}
                    </div>
                  )}

                  {Array.isArray(order.items) && (order.items as Array<{ product_name?: string; product_id?: string; quantity?: number; unit_price?: number }>).length > 0 && (
                    <ul style={{ marginBottom: "0.6rem", marginLeft: "2rem", fontSize: "0.9rem", margin: 0, paddingLeft: "1.5rem" }}>
                      {(order.items as Array<{ product_name?: string; product_id?: string; quantity?: number; unit_price?: number }>).map((item, itemIdx) => (
                        <li key={`checkpoint-order-${idx}-item-${itemIdx}`}>
                          {item.product_name || item.product_id || "Onbekend product"} — {item.quantity ?? 0} stuks @ {formatCurrency(item.unit_price ?? 0)}
                        </li>
                      ))}
                    </ul>
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
                        fontFamily: "inherit",
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
          disabled={submitting || isLoading || (draftOrders.length > 0 && !allOrdersHaveDecision)}
          style={{
            padding: "0.8rem 1.5rem",
            backgroundColor: "#ff8800",
            color: "white",
            border: "none",
            borderRadius: "6px",
            fontWeight: "bold",
            cursor: submitting || isLoading ? "not-allowed" : "pointer",
            opacity: submitting || isLoading || (draftOrders.length > 0 && !allOrdersHaveDecision) ? 0.6 : 1,
          }}
        >
          {submitting
            ? "Verwerken..."
            : draftOrders.length === 0
              ? "Geen bestellingen"
              : "📋 Beslissing Afronden"}
        </button>

        {draftOrders.length > 0 && !allOrdersHaveDecision && (
          <div style={{ color: "#b42318", fontSize: "0.9rem" }}>
            Validatie: geef voor elke bestelling een keuze (goedgekeurd of afwijsreden) voordat je kunt doorgaan.
          </div>
        )}
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
        {checkpoint?.message || state?.message || "Voorstel gereed voor verwerking."}
      </p>

      {draftOrders.length > 0 && (
        <div style={{ marginBottom: "1rem", maxHeight: "200px", overflowY: "auto", fontSize: "0.9rem" }}>
          {draftOrders.map((order, idx) => {
            const orderType = getOrderType(order);
            const orderSourceLabel = getOrderSourceLabel(order);
            return (
              <div key={`proposal-order-${idx}`} style={{ marginBottom: "0.5rem", color: "#555" }}>
                <strong>{order.supplier_name || `Voorstel ${idx + 1}`}</strong>
                <span
                  style={{
                    marginLeft: "0.5rem",
                    backgroundColor: orderType === "New Release" ? "#fef3c7" : "#e0e7ff",
                    padding: "0.15rem 0.45rem",
                    borderRadius: "3px",
                    fontWeight: 700,
                    color: "#111827",
                  }}
                >
                  {orderType}
                </span>
                <span style={{ marginLeft: "0.4rem", fontSize: "0.8rem", color: "#475467" }}>{orderSourceLabel}</span>
                {order.ai_recommendation && (
                  <div style={{ fontSize: "0.85rem", marginTop: "0.25rem", color: "#666" }}>
                    → {String(order.ai_recommendation).substring(0, 60)}...
                  </div>
                )}
              </div>
            );
          })}
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
