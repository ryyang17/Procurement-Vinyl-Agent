"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  CopilotKit,
  CopilotSidebar,
  UseAgentUpdate,
  useAgent,
} from "@copilotkit/react-core/v2";

import "@copilotkit/react-core/v2/styles.css";
import "./style.css";
import {
  CheckpointStateResponse,
  INITIAL_AGENT_STATE,
  PendingCheckpointItem,
  PendingCheckpointResponse,
  ProcurementDraftOrder,
  ProcurementAgentState,
  SalesVelocityForecast,
  formatCurrency,
} from "./agent";
import ApprovalPanel from "./components/ApprovalPanel";

const AGENT_ID = "procurement_agent";

type SharedStateFocus = "inventory" | "suppliers" | "approvals" | "workflow";

type ProposalHistoryItem = PendingCheckpointItem & {
  resolved_decision: "approved" | "rejected";
  resolved_at: string;
  approved_indices?: number[];
  rejection_reasons_by_index?: Record<number, string>;
};

type CheckpointDecisionState = {
  approvalsByIndex: Record<number, boolean>;
  rejectionReasonsByIndex: Record<number, string>;
};

function toFriendlyLabel(value?: string, maxLength = 24): string {
  if (!value) return "-";
  const normalized = value
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  const titled = normalized.replace(/\b\w/g, (char) => char.toUpperCase());
  if (titled.length <= maxLength) return titled;
  return `${titled.slice(0, maxLength - 1)}...`;
}

function formatRelativeTime(value?: string): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "-";

  const deltaMs = Date.now() - parsed.getTime();
  const deltaMin = Math.round(deltaMs / 60000);
  if (deltaMin < 1) return "zojuist";
  if (deltaMin < 60) return `${deltaMin} min geleden`;
  const deltaHours = Math.round(deltaMin / 60);
  if (deltaHours < 24) return `${deltaHours} uur geleden`;
  const deltaDays = Math.round(deltaHours / 24);
  return `${deltaDays} dag(en) geleden`;
}

function normalizeCheckpointState(payload: CheckpointStateResponse): ProcurementAgentState {
  const rawState = payload?.state;
  const stateObject = rawState && typeof rawState === "object" ? rawState : {};
  const mergedDraftOrders = Array.isArray(stateObject.draft_orders)
    ? stateObject.draft_orders
    : Array.isArray(payload.draft_orders)
      ? payload.draft_orders
      : [];

  return {
    ...INITIAL_AGENT_STATE,
    ...stateObject,
    draft_orders: mergedDraftOrders,
  };
}

function Dashboard() {
  const { agent } = useAgent({
    agentId: AGENT_ID,
    updates: [UseAgentUpdate.OnStateChanged, UseAgentUpdate.OnRunStatusChanged],
  });

  const state = (agent.state as ProcurementAgentState) || INITIAL_AGENT_STATE;
  const [pendingCheckpoints, setPendingCheckpoints] = useState<PendingCheckpointItem[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [checkpointLoadId, setCheckpointLoadId] = useState<string | null>(null);
  const [checkpointDecisionSubmittingId, setCheckpointDecisionSubmittingId] = useState<string | null>(null);
  const [checkpointNotice, setCheckpointNotice] = useState<string | null>(null);
  const [lastSharedSync, setLastSharedSync] = useState<string>("Nog niet gesynchroniseerd");
  const [proposalHistory, setProposalHistory] = useState<ProposalHistoryItem[]>([]);
  const [checkpointDecisions, setCheckpointDecisions] = useState<Record<string, CheckpointDecisionState>>({});

  useEffect(() => {
    if (!agent.state) {
      agent.setState(INITIAL_AGENT_STATE);
    }
  }, [agent]);

  const fetchPendingCheckpoints = async () => {
    try {
      setPendingLoading(true);
      setPendingError(null);
      const response = await fetch("/api/checkpoints/pending?limit=50", {
        method: "GET",
        cache: "no-store",
      });
      const payload = (await response.json()) as PendingCheckpointResponse | { error?: string };

      if (!response.ok) {
        const message = "error" in payload ? payload.error || "Onbekende fout" : "Onbekende fout";
        throw new Error(message);
      }

      const normalizedItems = ((payload as PendingCheckpointResponse).items || []).filter(
        (item) => Boolean(String(item.thread_id || "").trim())
      );
      setPendingCheckpoints(normalizedItems);

      setCheckpointDecisions((prev) => {
        const next: Record<string, CheckpointDecisionState> = {};

        for (const item of normalizedItems) {
          const existing = prev[item.thread_id];
          if (existing) {
            next[item.thread_id] = existing;
            continue;
          }

          const approvalsByIndex: Record<number, boolean> = {};
          for (let idx = 0; idx < item.draft_orders_count; idx += 1) {
            approvalsByIndex[idx] = true;
          }

          next[item.thread_id] = {
            approvalsByIndex,
            rejectionReasonsByIndex: {},
          };
        }

        return next;
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setPendingError(message);
    } finally {
      setPendingLoading(false);
    }
  };

  const loadCheckpointIntoDashboard = async (threadId: string) => {
    const normalizedThreadId = String(threadId || "").trim();

    try {
      if (!normalizedThreadId) {
        throw new Error("Checkpoint heeft geen geldige thread-id en kan niet geladen worden.");
      }

      setPendingError(null);
      setCheckpointNotice(null);
      setCheckpointLoadId(normalizedThreadId);

      const response = await fetch(`/api/checkpoints/${encodeURIComponent(normalizedThreadId)}`, {
        method: "GET",
        cache: "no-store",
      });
      const payload = (await response.json()) as CheckpointStateResponse | { error?: string };

      if (!response.ok) {
        const message = "error" in payload ? payload.error || "Onbekende fout" : "Onbekende fout";
        throw new Error(message);
      }

      const checkpointPayload = payload as CheckpointStateResponse;
      const rawState = checkpointPayload.state && typeof checkpointPayload.state === "object"
        ? checkpointPayload.state
        : null;
      const hasRawState = Boolean(rawState && Object.keys(rawState).length > 0);
      const hasDraftOrders = Array.isArray(checkpointPayload.draft_orders) && checkpointPayload.draft_orders.length > 0;
      if (!hasRawState && !hasDraftOrders) {
        throw new Error("Checkpoint bevat geen laadbare state.");
      }

      const normalizedState = normalizeCheckpointState(checkpointPayload);

      agent.setState(normalizedState);
      setActiveThreadId(normalizedThreadId);
      setCheckpointNotice(`Checkpoint geladen: ${normalizedThreadId}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setPendingError(message);
    } finally {
      setCheckpointLoadId(null);
    }
  };

  const submitCheckpointDecision = async (threadId: string, approveAll: boolean) => {
    try {
      setPendingError(null);
      const checkpoint = pendingCheckpoints.find((item) => item.thread_id === threadId);
      const draftCount = checkpoint?.draft_orders_count || 0;
      const allIndices = Array.from({ length: draftCount }, (_, idx) => idx);

      const rejectionReasonsByIndex = approveAll
        ? {}
        : Object.fromEntries(allIndices.map((idx) => [idx, "Afgewezen via frontend checkpointpanel"]));

      const response = await fetch(`/api/checkpoints/${encodeURIComponent(threadId)}/decision`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          approved_indices: approveAll ? allIndices : [],
          rejection_reasons_by_index: rejectionReasonsByIndex,
          approved_by: "frontend_manager",
          decision: approveAll ? "approved" : "rejected",
        }),
      });

      const payload = (await response.json()) as CheckpointStateResponse | { error?: string };
      if (!response.ok) {
        const message = "error" in payload ? payload.error || "Onbekende fout" : "Onbekende fout";
        throw new Error(message);
      }

      const statePayload = (payload as CheckpointStateResponse).state;
      agent.setState(statePayload);
      setActiveThreadId(threadId);

      if (checkpoint) {
        setProposalHistory((prev) => [
          {
            ...checkpoint,
            resolved_decision: approveAll ? "approved" : "rejected",
            resolved_at: new Date().toISOString(),
            approved_indices: approveAll ? allIndices : [],
            rejection_reasons_by_index: rejectionReasonsByIndex,
          },
          ...prev.filter((item) => item.thread_id !== threadId),
        ]);
      }

      setPendingCheckpoints((prev) => prev.filter((item) => item.thread_id !== threadId));
      await fetchPendingCheckpoints();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setPendingError(message);
    }
  };

  const toggleCheckpointOrderApproval = (threadId: string, orderIndex: number, approved: boolean) => {
    setCheckpointDecisions((prev) => {
      const current = prev[threadId] || { approvalsByIndex: {}, rejectionReasonsByIndex: {} };
      const nextReasons = { ...current.rejectionReasonsByIndex };

      if (approved) {
        delete nextReasons[orderIndex];
      }

      return {
        ...prev,
        [threadId]: {
          approvalsByIndex: {
            ...current.approvalsByIndex,
            [orderIndex]: approved,
          },
          rejectionReasonsByIndex: nextReasons,
        },
      };
    });
  };

  const setCheckpointRejectionReason = (threadId: string, orderIndex: number, reason: string) => {
    setCheckpointDecisions((prev) => {
      const current = prev[threadId] || { approvalsByIndex: {}, rejectionReasonsByIndex: {} };
      return {
        ...prev,
        [threadId]: {
          approvalsByIndex: {
            ...current.approvalsByIndex,
          },
          rejectionReasonsByIndex: {
            ...current.rejectionReasonsByIndex,
            [orderIndex]: reason,
          },
        },
      };
    });
  };

  const submitCheckpointDetailedDecision = async (threadId: string) => {
    try {
      setPendingError(null);
      setCheckpointNotice(null);
      setCheckpointDecisionSubmittingId(threadId);

      const checkpoint = pendingCheckpoints.find((item) => item.thread_id === threadId);
      if (!checkpoint) {
        throw new Error("Checkpoint niet gevonden.");
      }

      const localDecision = checkpointDecisions[threadId];
      const approvedIndices = Array.from({ length: checkpoint.draft_orders_count }, (_, idx) => idx)
        .filter((idx) => localDecision?.approvalsByIndex[idx] ?? true);

      const rejectionReasonsByIndex = Object.fromEntries(
        Object.entries(localDecision?.rejectionReasonsByIndex || {})
          .filter(([idx]) => !approvedIndices.includes(Number(idx)))
      );

      const response = await fetch(`/api/checkpoints/${encodeURIComponent(threadId)}/decision`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          approved_indices: approvedIndices,
          rejection_reasons_by_index: rejectionReasonsByIndex,
          approved_by: "frontend_manager",
          decision: approvedIndices.length > 0 ? "approved" : "rejected",
        }),
      });

      const payload = (await response.json()) as CheckpointStateResponse | { error?: string };
      if (!response.ok) {
        const message = "error" in payload ? payload.error || "Onbekende fout" : "Onbekende fout";
        throw new Error(message);
      }

      const resolvedDecision: "approved" | "rejected" = approvedIndices.length > 0 ? "approved" : "rejected";

      setProposalHistory((prev) => [
        {
          ...checkpoint,
          resolved_decision: resolvedDecision,
          resolved_at: new Date().toISOString(),
          approved_indices: approvedIndices,
          rejection_reasons_by_index: rejectionReasonsByIndex,
        },
        ...prev.filter((item) => item.thread_id !== threadId),
      ]);

      setCheckpointDecisions((prev) => {
        const next = { ...prev };
        delete next[threadId];
        return next;
      });

      setPendingCheckpoints((prev) => prev.filter((item) => item.thread_id !== threadId));

      const statePayload = (payload as CheckpointStateResponse).state;
      agent.setState(statePayload);
      setActiveThreadId(threadId);
      setCheckpointNotice(
        `Checkpoint ${threadId} verwerkt: ${approvedIndices.length} album(s) goedgekeurd. Workflow vervolgd voor plaatsing en afronding.`
      );

      await fetchPendingCheckpoints();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setPendingError(message);
    } finally {
      setCheckpointDecisionSubmittingId(null);
    }
  };

  const submitActiveThreadDecision = async (
    approvedIndices: number[],
    rejectionReasonsByIndex: Record<number, string>
  ) => {
    if (!activeThreadId) {
      throw new Error("Geen actieve checkpoint-thread geladen.");
    }

    const response = await fetch(`/api/checkpoints/${encodeURIComponent(activeThreadId)}/decision`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        approved_indices: approvedIndices,
        rejection_reasons_by_index: rejectionReasonsByIndex,
        approved_by: "frontend_manager",
        decision: approvedIndices.length > 0 ? "approved" : "rejected",
      }),
    });

    const payload = (await response.json()) as CheckpointStateResponse | { error?: string };
    if (!response.ok) {
      const message = "error" in payload ? payload.error || "Onbekende fout" : "Onbekende fout";
      throw new Error(message);
    }

    const checkpoint = pendingCheckpoints.find((item) => item.thread_id === activeThreadId);
    if (checkpoint) {
      setProposalHistory((prev) => [
        {
          ...checkpoint,
          resolved_decision: approvedIndices.length > 0 ? "approved" : "rejected",
          resolved_at: new Date().toISOString(),
          approved_indices: approvedIndices,
          rejection_reasons_by_index: rejectionReasonsByIndex,
        },
        ...prev.filter((item) => item.thread_id !== activeThreadId),
      ]);
    }

    setPendingCheckpoints((prev) => prev.filter((item) => item.thread_id !== activeThreadId));
    setCheckpointNotice(`Beslissing verwerkt voor thread: ${activeThreadId}`);

    const statePayload = (payload as CheckpointStateResponse).state;
    agent.setState(statePayload);
    await fetchPendingCheckpoints();
  };

  useEffect(() => {
    fetchPendingCheckpoints();
    const interval = setInterval(fetchPendingCheckpoints, 15000);
    return () => clearInterval(interval);
  }, []);

  const kpis = useMemo(() => {
    const alerts = state.inventory_alerts?.length ?? 0;
    const offers = state.supplier_offers?.length ?? 0;
    const draftOrders = state.draft_orders?.length ?? 0;
    const approvals = state.approved_orders?.length ?? 0;
    return { alerts, offers, draftOrders, approvals };
  }, [state]);

  const salesVelocityForecasts = useMemo(() => {
    const forecasts = state.data?.sales_velocity_forecasts;
    return Array.isArray(forecasts) ? forecasts : [];
  }, [state.data]);

  const draftOrderTypeSummary = useMemo(() => {
    const orders = state.draft_orders || [];
    let reorder = 0;
    let newRelease = 0;

    for (const order of orders) {
      const source = String(order.source_type || order.order_path || "").toLowerCase();
      if (source.includes("new_release") || source.includes("new_releases")) {
        newRelease += 1;
      } else {
        reorder += 1;
      }
    }

    return { reorder, newRelease };
  }, [state.draft_orders]);

  const syncSharedState = (focus: SharedStateFocus) => {
    const sharedSnapshot = {
      focus,
      synced_at: new Date().toISOString(),
      kpis,
      pending_checkpoints: pendingCheckpoints.length,
      active_thread: activeThreadId,
      inventory_alerts_preview: (state.inventory_alerts || []).slice(0, 5),
      sales_velocity_alerts_preview: (state.sales_velocity_alerts || []).slice(0, 5),
      draft_order_summary: draftOrderTypeSummary,
    };

    agent.setState({
      ...state,
      data: {
        ...(state.data || {}),
        shared_ui_context: sharedSnapshot,
      },
      summary: `UI context gesynchroniseerd voor focus: ${focus}`,
    });

    setLastSharedSync(`Gesynchroniseerd: ${new Date().toLocaleTimeString("nl-NL")}`);
  };

  return (
    <div className="vinyl-layout">
      <div className="vinyl-main">
        <header className="vinyl-header">
          <h1>Vinyl Inkoop Dashboard</h1>
          <p>Realtime overzicht van voorraad, leveranciers en approvals</p>
        </header>

        <section className="kpi-grid">
          <div className="kpi-card">
            <span>Voorraad Alerts</span>
            <strong>{kpis.alerts}</strong>
          </div>
          <div className="kpi-card">
            <span>Supplier Offers</span>
            <strong>{kpis.offers}</strong>
          </div>
          <div className="kpi-card">
            <span>Draft Orders</span>
            <strong>{kpis.draftOrders}</strong>
          </div>
          <div className="kpi-card">
            <span>Approved Orders</span>
            <strong>{kpis.approvals}</strong>
          </div>
        </section>

        <section className="panel panel-checkpoints">
          <details open>
            <summary className="panel-summary">
              <span>Openstaande Checkpoints</span>
              <span className="summary-chip">{pendingCheckpoints.length} actief</span>
            </summary>

            <p style={{ marginBottom: "1rem" }}>
              Compact overzicht. Klik per checkpoint voor details en acties.
            </p>

            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", alignItems: "center", flexWrap: "wrap" }}>
              <button className="btn btn-soft" onClick={fetchPendingCheckpoints}>
                Vernieuwen
              </button>
              {pendingLoading && <span>Bezig met laden...</span>}
              <span className="summary-chip">Actieve thread: {activeThreadId ? "geladen" : "geen"}</span>
            </div>

            {pendingError && (
              <div style={{ color: "#b42318", marginBottom: "1rem" }}>
                Fout bij ophalen/verwerken checkpoints: {pendingError}
              </div>
            )}

            {checkpointNotice && (
              <div style={{ color: "#027a48", marginBottom: "1rem" }}>
                {checkpointNotice}
              </div>
            )}

            {pendingCheckpoints.length === 0 ? (
              <p>Geen openstaande checkpoints gevonden.</p>
            ) : (
              <div style={{ display: "grid", gap: "0.8rem" }}>
                {pendingCheckpoints.map((item, idx) => (
                  <details
                    key={item.thread_id}
                    className="checkpoint-card"
                    open={activeThreadId === item.thread_id}
                  >
                    <summary className="checkpoint-summary">
                      <span className="checkpoint-title">Checkpoint {idx + 1}</span>
                      <span className="checkpoint-meta">
                        <span className="summary-chip summary-chip-green">{toFriendlyLabel(item.status, 18)}</span>
                        <span className="summary-chip">{toFriendlyLabel(item.step, 20)}</span>
                        <span className="summary-chip summary-chip-blue">{item.draft_orders_count} orders</span>
                        <span className="summary-chip">{formatRelativeTime(item.updated_at || item.approval_requested_at)}</span>
                      </span>
                    </summary>

                    <div className="checkpoint-body">
                      <div style={{ color: "#475467", fontSize: "0.9rem" }}>
                        Technisch ID: {item.thread_id}
                      </div>
                      <div style={{ marginTop: "0.45rem", color: "#1f2937" }}>{item.message || "Geen extra bericht"}</div>

                      <div style={{ marginTop: "0.65rem", color: "#344054", fontSize: "0.92rem" }}>
                        Kies per album goedkeuren of afwijzen. Na indienen gaat de thread direct door met bestellen en afronden.
                      </div>

                      {(item.draft_orders || []).length > 0 && (
                        <div style={{ marginTop: "0.7rem", display: "grid", gap: "0.5rem" }}>
                          {(item.draft_orders || []).map((order, orderIdx) => (
                            <div
                              key={`checkpoint-${item.thread_id}-order-${orderIdx}`}
                              style={{ border: "1px solid #e4e7ec", borderRadius: "8px", padding: "0.6rem", backgroundColor: "#fcfcfd" }}
                            >
                              <strong>{order.supplier_name || `Leverancier ${orderIdx + 1}`}</strong>
                              <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.7rem", alignItems: "center", flexWrap: "wrap" }}>
                                <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontWeight: 500 }}>
                                  <input
                                    type="radio"
                                    name={`decision-${item.thread_id}-${orderIdx}`}
                                    checked={(checkpointDecisions[item.thread_id]?.approvalsByIndex[orderIdx] ?? true) === true}
                                    onChange={() => toggleCheckpointOrderApproval(item.thread_id, orderIdx, true)}
                                  />
                                  Goedkeuren
                                </label>
                                <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", fontWeight: 500 }}>
                                  <input
                                    type="radio"
                                    name={`decision-${item.thread_id}-${orderIdx}`}
                                    checked={(checkpointDecisions[item.thread_id]?.approvalsByIndex[orderIdx] ?? true) === false}
                                    onChange={() => toggleCheckpointOrderApproval(item.thread_id, orderIdx, false)}
                                  />
                                  Afwijzen
                                </label>
                              </div>
                              {typeof order.ai_recommendation === "string" && order.ai_recommendation.trim() && (
                                <div style={{ marginTop: "0.35rem", color: "#344054", fontSize: "0.9rem" }}>
                                  Reden voorstel: {order.ai_recommendation}
                                </div>
                              )}
                              <ul className="list" style={{ marginTop: "0.45rem" }}>
                                {(order.items || []).map((draftItem, itemIdx) => (
                                  <li key={`checkpoint-${item.thread_id}-order-${orderIdx}-item-${itemIdx}`}>
                                    {draftItem.product_name || draftItem.product_id || "Onbekend album"} - {draftItem.quantity ?? 0} stuks
                                  </li>
                                ))}
                              </ul>

                              {(checkpointDecisions[item.thread_id]?.approvalsByIndex[orderIdx] ?? true) === false && (
                                <div style={{ marginTop: "0.6rem" }}>
                                  <label style={{ display: "block", fontSize: "0.9rem", marginBottom: "0.4rem" }}>
                                    Reden afwijzing (optioneel)
                                  </label>
                                  <textarea
                                    value={checkpointDecisions[item.thread_id]?.rejectionReasonsByIndex[orderIdx] ?? ""}
                                    onChange={(e) => setCheckpointRejectionReason(item.thread_id, orderIdx, e.target.value)}
                                    placeholder="Bijv. te duur of te lange levertijd"
                                    style={{
                                      width: "100%",
                                      padding: "0.5rem",
                                      borderRadius: "6px",
                                      border: "1px solid #d0d5dd",
                                      fontFamily: "inherit",
                                      minHeight: "56px",
                                    }}
                                  />
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.8rem", flexWrap: "wrap" }}>
                        <button
                          className="btn btn-primary"
                          onClick={() => loadCheckpointIntoDashboard(item.thread_id)}
                          disabled={checkpointLoadId === item.thread_id}
                        >
                          {checkpointLoadId === item.thread_id ? "Laden..." : "Laden in dashboard"}
                        </button>
                        <button className="btn btn-success" onClick={() => submitCheckpointDecision(item.thread_id, true)}>
                          Alles goedkeuren
                        </button>
                        <button className="btn btn-danger" onClick={() => submitCheckpointDecision(item.thread_id, false)}>
                          Alles afwijzen
                        </button>
                        <button
                          className="btn btn-soft"
                          onClick={() => submitCheckpointDetailedDecision(item.thread_id)}
                          disabled={checkpointDecisionSubmittingId === item.thread_id}
                        >
                          {checkpointDecisionSubmittingId === item.thread_id
                            ? "Beslissing verwerken..."
                            : "Per album indienen en workflow afronden"}
                        </button>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            )}
          </details>
        </section>

        {/* Show ApprovalPanel if awaiting_human_approval is true AND there are draft orders (including reorder-only) */}
        {state.awaiting_human_approval && Array.isArray(state.draft_orders) && state.draft_orders.length > 0 && (
          <ApprovalPanel
            state={state}
            agent={agent}
            onSubmitCheckpointDecision={activeThreadId ? submitActiveThreadDecision : undefined}
          />
        )}

        <section className="panel panel-workflow">
          <details open>
            <summary className="panel-summary">
              <span>Samengevoegde Workflow</span>
            </summary>
            <p style={{ marginBottom: "0.6rem" }}>
              Deze run gaat automatisch door: marktonderzoek naar new releases, daarna suppliers, create orders en human approval.
            </p>
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <span className="summary-chip summary-chip-green">New release orders: {draftOrderTypeSummary.newRelease}</span>
              <span className="summary-chip summary-chip-blue">Reorder orders: {draftOrderTypeSummary.reorder}</span>
            </div>
          </details>
        </section>

        <section className="panel panel-shared-state">
          <details open>
            <summary className="panel-summary">
              <span>Shared State Snelkoppelingen</span>
              <span className="summary-chip">{lastSharedSync}</span>
            </summary>
            <p style={{ marginBottom: "0.8rem" }}>
              Houd app en agent synchroon. De agent leest deze UI-context direct uit state.data.shared_ui_context.
            </p>
            <div style={{ display: "flex", gap: "0.55rem", flexWrap: "wrap" }}>
              <button className="btn btn-primary" onClick={() => syncSharedState("inventory")}>Sync Voorraad</button>
              <button className="btn btn-success" onClick={() => syncSharedState("suppliers")}>Sync Leveranciers</button>
              <button className="btn btn-soft" onClick={() => syncSharedState("approvals")}>Sync Approvals</button>
              <button className="btn btn-danger" onClick={() => syncSharedState("workflow")}>Sync Workflow</button>
            </div>
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Workflow Status</span>
            </summary>
            <div className="status-row">
              <div>
                <label>Stap</label>
                <p>{state.step || "-"}</p>
              </div>
              <div>
                <label>Volgende Actie</label>
                <p>{state.next_action || "-"}</p>
              </div>
              <div>
                <label>Approval</label>
                <p>{state.approval_decision || "-"}</p>
              </div>
            </div>
            <div className="summary-box">
              {state.summary || "Nog geen samenvatting beschikbaar."}
            </div>
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Voorraad Meldingen</span>
              <span className="summary-chip">{(state.inventory_alerts || []).length}</span>
            </summary>
            <ul className="list">
              {(state.inventory_alerts || []).length === 0 && <li>Geen meldingen</li>}
              {(state.inventory_alerts || []).map((alert, idx) => (
                <li key={`${alert}-${idx}`}>{alert}</li>
              ))}
            </ul>
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Sales Velocity Forecasts</span>
              <span className="summary-chip">{salesVelocityForecasts.length}</span>
            </summary>
            <ul className="list" style={{ marginBottom: "0.8rem" }}>
              {(state.sales_velocity_alerts || []).length === 0 && <li>Geen urgente velocity alerts</li>}
              {(state.sales_velocity_alerts || []).map((alert, idx) => (
                <li key={`velocity-alert-${idx}`}>{alert}</li>
              ))}
            </ul>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Velocity / dag</th>
                    <th>Stockout datum</th>
                    <th>Reorder basis</th>
                  </tr>
                </thead>
                <tbody>
                  {salesVelocityForecasts.length === 0 && (
                    <tr>
                      <td colSpan={4}>Nog geen sales velocity data</td>
                    </tr>
                  )}
                  {salesVelocityForecasts.map((forecast: SalesVelocityForecast, idx: number) => (
                    <tr key={`velocity-${forecast.product_id ?? idx}`}>
                      <td>{forecast.product_name || forecast.product_id || "-"}</td>
                      <td>
                        {typeof forecast.velocity_per_day === "number"
                          ? forecast.velocity_per_day.toFixed(2)
                          : "-"}
                      </td>
                      <td>{forecast.predicted_stockout_date || "-"}</td>
                      <td>{forecast.reorder_basis || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Supplier Offers</span>
              <span className="summary-chip">{(state.supplier_offers || []).length}</span>
            </summary>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th>Product</th>
                    <th>Prijs</th>
                    <th>Levertijd</th>
                    <th>Betrouwbaarheid</th>
                  </tr>
                </thead>
                <tbody>
                  {(state.supplier_offers || []).length === 0 && (
                    <tr>
                      <td colSpan={5}>Nog geen offers</td>
                    </tr>
                  )}
                  {(state.supplier_offers || []).map((offer, idx) => (
                    <tr key={`offer-${idx}`}>
                      <td>{offer.supplier_name || offer.supplier_id || "-"}</td>
                      <td>{offer.notes || "-"}</td>
                      <td>{formatCurrency(offer.unit_price)}</td>
                      <td>
                        {typeof offer.lead_time_days === "number"
                          ? `${offer.lead_time_days} d`
                          : "-"}
                      </td>
                      <td>
                        {typeof offer.reliability_score === "number"
                          ? offer.reliability_score.toFixed(2)
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Inkoopvoorstel History</span>
              <span className="summary-chip">{proposalHistory.length + (state.draft_orders || []).length}</span>
            </summary>

            {proposalHistory.length === 0 && (state.draft_orders || []).length === 0 && <p>Nog geen voorstellen in history</p>}

            {proposalHistory.length > 0 && (
              <div style={{ display: "grid", gap: "0.8rem", marginBottom: "1rem" }}>
                {proposalHistory.map((entry, idx) => (
                  <details key={`history-thread-${entry.thread_id}-${idx}`} className="draft-card">
                    <summary className="checkpoint-summary">
                      <span className="checkpoint-title">Thread {entry.thread_id}</span>
                      <span className="checkpoint-meta">
                        <span className={`summary-chip ${entry.resolved_decision === "approved" ? "summary-chip-green" : "summary-chip"}`}>
                          {entry.resolved_decision === "approved" ? "Goedgekeurd" : "Afgewezen"}
                        </span>
                        <span className="summary-chip summary-chip-blue">{entry.draft_orders_count} orders</span>
                        <span className="summary-chip">{formatRelativeTime(entry.resolved_at)}</span>
                      </span>
                    </summary>

                    <div style={{ display: "grid", gap: "0.55rem", marginTop: "0.45rem" }}>
                      {(entry.draft_orders || []).length === 0 && <p>Geen orderdetails beschikbaar</p>}
                      {(entry.draft_orders || []).map((order, orderIdx) => (
                        <div key={`history-order-${entry.thread_id}-${orderIdx}`} style={{ border: "1px solid #e4e7ec", borderRadius: "8px", padding: "0.6rem" }}>
                          <strong>{order.supplier_name || `Leverancier ${orderIdx + 1}`}</strong>
                          {typeof order.ai_recommendation === "string" && order.ai_recommendation.trim() && (
                            <div style={{ marginTop: "0.35rem", color: "#344054", fontSize: "0.9rem" }}>
                              Reden voorstel: {order.ai_recommendation}
                            </div>
                          )}
                          {entry.rejection_reasons_by_index && typeof entry.rejection_reasons_by_index[orderIdx] === "string" && (
                            <div style={{ marginTop: "0.35rem", color: "#b42318", fontSize: "0.9rem" }}>
                              Reden afwijzing: {entry.rejection_reasons_by_index[orderIdx]}
                            </div>
                          )}
                          <ul className="list" style={{ marginTop: "0.45rem" }}>
                            {(order.items || []).length === 0 && <li>Geen items</li>}
                            {(order.items || []).map((item, itemIdx) => (
                              <li key={`history-order-${entry.thread_id}-${orderIdx}-item-${itemIdx}`}>
                                {item.product_name || item.product_id || "Onbekend product"} - {item.quantity ?? 0} stuks @ {formatCurrency(item.unit_price)}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            )}

            <div style={{ display: "grid", gap: "0.8rem" }}>
              {(state.draft_orders || []).map((order: ProcurementDraftOrder, idx) => (
                <details key={`draft-${idx}`} className="draft-card">
                  <summary className="checkpoint-summary">
                    <span className="checkpoint-title">Actief voorstel: {order.supplier_name || `Leverancier ${idx + 1}`}</span>
                    <span className="checkpoint-meta">
                      <span className="summary-chip">
                        {String(order.source_type || order.order_path || "").toLowerCase().includes("new_release") ? "New Release" : "Reorder"}
                      </span>
                      <span className="summary-chip summary-chip-blue">
                        {formatCurrency(typeof order.total_amount === "number" ? order.total_amount : (order.items || []).reduce((acc, item) => acc + (item.quantity ?? 0) * (item.unit_price ?? 0), 0))}
                      </span>
                    </span>
                  </summary>

                  {order.ai_recommendation && (
                    <div style={{ marginTop: "0.45rem", color: "#344054", fontSize: "0.92rem" }}>
                      Reden voorstel: {order.ai_recommendation}
                    </div>
                  )}

                  <ul className="list" style={{ marginTop: "0.45rem" }}>
                    {(order.items || []).length === 0 && <li>Geen items</li>}
                    {(order.items || []).map((item, itemIdx) => (
                      <li key={`draft-${idx}-item-${itemIdx}`}>
                        {item.product_name || item.product_id || "Onbekend product"} - {item.quantity ?? 0} stuks @ {formatCurrency(item.unit_price)}
                      </li>
                    ))}
                  </ul>
                </details>
              ))}
            </div>
          </details>
        </section>
      </div>

      <aside className="vinyl-chat">
        <CopilotSidebar
          agentId={AGENT_ID}
          defaultOpen={true}
          labels={{ modalHeaderTitle: "Vinyl Inkoop Assistent" }}
        />
      </aside>
    </div>
  );
}

export default function Page() {
  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      showDevConsole={false}
      agent={AGENT_ID}
    >
      <Dashboard />
    </CopilotKit>
  );
}

