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
import CheckpointActionPanel from "./components/CheckpointActionPanel";

const AGENT_ID = "procurement_agent";


type ProposalHistoryItem = PendingCheckpointItem & {
  resolved_decision: "approved" | "rejected";
  resolved_at: string;
  approved_indices?: number[];
  rejection_reasons_by_index?: Record<number, string>;
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
  const [checkpointNotice, setCheckpointNotice] = useState<string | null>(null);
  const [proposalHistory, setProposalHistory] = useState<ProposalHistoryItem[]>([]);
  const [activeCheckpointItem, setActiveCheckpointItem] = useState<PendingCheckpointItem | null>(null);

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
      const selected = pendingCheckpoints.find((item) => item.thread_id === normalizedThreadId) || null;

      agent.setState(normalizedState);
      setActiveThreadId(normalizedThreadId);
      setActiveCheckpointItem(selected);
      setCheckpointNotice(`Checkpoint geladen: ${normalizedThreadId}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setPendingError(message);
    } finally {
      setCheckpointLoadId(null);
    }
  };

  const submitActiveThreadDecision = async (
    approvedIndices: number[],
    rejectionReasonsByIndex: Record<number, string>,
    threadId?: string
  ) => {
    const targetThreadId = threadId || activeThreadId;
    if (!targetThreadId) {
      throw new Error("Geen actieve checkpoint-thread geladen.");
    }

    const response = await fetch(`/api/checkpoints/${encodeURIComponent(targetThreadId)}/decision`, {
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

    const checkpoint =
      pendingCheckpoints.find((item) => item.thread_id === targetThreadId) ||
      (activeCheckpointItem?.thread_id === targetThreadId ? activeCheckpointItem : null);
    if (checkpoint) {
      setProposalHistory((prev) => [
        {
          ...checkpoint,
          resolved_decision: approvedIndices.length > 0 ? "approved" : "rejected",
          resolved_at: new Date().toISOString(),
          approved_indices: approvedIndices,
          rejection_reasons_by_index: rejectionReasonsByIndex,
        },
        ...prev.filter((item) => item.thread_id !== targetThreadId),
      ]);
    }

    setPendingCheckpoints((prev) => prev.filter((item) => item.thread_id !== targetThreadId));
    setCheckpointNotice(`Beslissing verwerkt voor thread: ${targetThreadId}. Doorgezet naar process approval en afronding.`);
    setActiveCheckpointItem(null);

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

                      {(item.draft_orders || []).length > 0 && (
                        <div style={{ marginTop: "0.7rem", display: "grid", gap: "0.5rem" }}>
                          {(item.draft_orders || []).map((order, orderIdx) => (
                            <div
                              key={`checkpoint-${item.thread_id}-order-${orderIdx}`}
                              style={{ border: "1px solid #e4e7ec", borderRadius: "8px", padding: "0.6rem", backgroundColor: "#fcfcfd" }}
                            >
                              <strong>{order.supplier_name || `Leverancier ${orderIdx + 1}`}</strong>
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
                            </div>
                          ))}
                        </div>
                      )}

                      <CheckpointActionPanel
                        checkpoint={item}
                        onSubmitDecision={(approvedIndices, rejectionReasonsByIndex) =>
                          submitActiveThreadDecision(approvedIndices, rejectionReasonsByIndex, item.thread_id)
                        }
                        isLoading={checkpointLoadId === item.thread_id}
                      />
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

        {/* Samengevoegde workflow paneel verwijderd */}

        {/* Shared state snelkoppelingen paneel verwijderd */}

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

      <CopilotSidebar
        agentId={AGENT_ID}
        defaultOpen={true}
        labels={{ modalHeaderTitle: "Vinyl Inkoop Assistent" }}
      />
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

