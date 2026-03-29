"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  CopilotKit,
  CopilotChat,
  UseAgentUpdate,
  useConfigureSuggestions,
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
  SupplierOffer,
  SalesVelocityForecast,
  formatCurrency,
} from "./agent";
import CheckpointActionPanel from "./components/CheckpointActionPanel";

const AGENT_ID = "procurement_agent";


type ProposalHistoryItem = PendingCheckpointItem & {
  resolved_decision: "approved" | "rejected";
  resolved_at: string;
  approved_indices?: number[];
  rejection_reasons_by_index?: Record<number, string>;
};

type ApprovedOrderSummary = {
  order_id?: number;
  supplier_id?: number;
  supplier_name?: string;
  status?: string;
  order_date?: string;
  expected_delivery_date?: string;
  delivery_date?: string;
  total_amount?: number;
  approved_by?: string;
  album_names?: string[];
};

type DashboardBootstrapResponse = {
  sales_velocity_forecasts?: SalesVelocityForecast[];
  approved_orders?: ApprovedOrderSummary[];
  supplier_offers?: SupplierOffer[];
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

function classifyAlertLevel(alert: string): "high" | "medium" | "low" {
  const normalized = alert.toLowerCase();
  if (
    normalized.includes("krit") ||
    normalized.includes("urgent") ||
    normalized.includes("stockout") ||
    normalized.includes("tekort") ||
    normalized.includes("out of stock")
  ) {
    return "high";
  }

  if (
    normalized.includes("waarschu") ||
    normalized.includes("risico") ||
    normalized.includes("vertraging") ||
    normalized.includes("laag")
  ) {
    return "medium";
  }

  return "low";
}

function classifyDraftOrder(order: ProcurementDraftOrder): "New Release" | "Reorder" {
  const NEW_RELEASE_WINDOW_DAYS = 5;
  const source = String(order.source_type || order.order_path || "").toLowerCase();
  const firstItem = Array.isArray(order.items) ? order.items[0] : undefined;
  const itemSource = String(firstItem?.source_type || firstItem?.order_path || "").toLowerCase();
  const recommendation = String(order.ai_recommendation || "").toLowerCase();
  const supplierName = String(order.supplier_name || "").toLowerCase();

  const parseDate = (raw?: string): Date | null => {
    if (!raw) return null;
    const parsed = new Date(raw);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const cutoff = new Date(Date.now() - NEW_RELEASE_WINDOW_DAYS * 24 * 60 * 60 * 1000);
  const releaseDate = parseDate(order.release_date || firstItem?.release_date);
  const createdAt = parseDate(order.created_at || firstItem?.created_at);

  if (
    source.includes("new_release") ||
    source.includes("new_releases") ||
    itemSource.includes("new_release") ||
    itemSource.includes("new_releases") ||
    supplierName.includes("spotify market suggestion") ||
    recommendation.includes("nieuwe release") ||
    recommendation.includes("spotify") ||
    typeof order.market_popularity_score === "number" ||
    Boolean(releaseDate && releaseDate >= cutoff) ||
    Boolean(createdAt && createdAt >= cutoff)
  ) {
    return "New Release";
  }

  return "Reorder";
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
  const [activeThreadId] = useState<string | null>(null);
  const [checkpointLoadId] = useState<string | null>(null);
  const [checkpointNotice, setCheckpointNotice] = useState<string | null>(null);
  const [proposalHistory, setProposalHistory] = useState<ProposalHistoryItem[]>([]);
  const [activeCheckpointItem, setActiveCheckpointItem] = useState<PendingCheckpointItem | null>(null);
  const [bootstrapSalesVelocityForecasts, setBootstrapSalesVelocityForecasts] = useState<SalesVelocityForecast[]>([]);
  const [bootstrapApprovedOrders, setBootstrapApprovedOrders] = useState<ApprovedOrderSummary[]>([]);
  const [bootstrapSupplierOffers, setBootstrapSupplierOffers] = useState<SupplierOffer[]>([]);

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

  const fetchDashboardBootstrap = async () => {
    try {
      const response = await fetch("/api/dashboard/bootstrap", {
        method: "GET",
        cache: "no-store",
      });

      const payload = (await response.json()) as DashboardBootstrapResponse | { error?: string };
      if (!response.ok) {
        return;
      }

      setBootstrapSalesVelocityForecasts(
        Array.isArray((payload as DashboardBootstrapResponse).sales_velocity_forecasts)
          ? (payload as DashboardBootstrapResponse).sales_velocity_forecasts || []
          : []
      );

      setBootstrapApprovedOrders(
        Array.isArray((payload as DashboardBootstrapResponse).approved_orders)
          ? (payload as DashboardBootstrapResponse).approved_orders || []
          : []
      );

      setBootstrapSupplierOffers(
        Array.isArray((payload as DashboardBootstrapResponse).supplier_offers)
          ? (payload as DashboardBootstrapResponse).supplier_offers || []
          : []
      );
    } catch {
      // Keep startup bootstrap best-effort; main dashboard should still render.
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
    fetchDashboardBootstrap();
    fetchPendingCheckpoints();
    const interval = setInterval(fetchPendingCheckpoints, 15000);
    return () => clearInterval(interval);
  }, []);

  const kpis = useMemo(() => {
    const alerts = state.inventory_alerts?.length ?? 0;
    const offers = state.supplier_offers?.length ?? 0;
    const directDraftOrders = Array.isArray(state.draft_orders) ? state.draft_orders : [];
    const nestedDraftOrders = Array.isArray(state.data?.draft_orders) ? state.data.draft_orders : [];
    const draftOrders = directDraftOrders.length + nestedDraftOrders.length;
    const approvals = state.approved_orders?.length ?? 0;
    return { alerts, offers, draftOrders, approvals };
  }, [state]);

  const activeDraftOrders = useMemo(() => {
    const directDraftOrders = Array.isArray(state.draft_orders)
      ? (state.draft_orders as ProcurementDraftOrder[])
      : [];
    const nestedDraftOrders = Array.isArray(state.data?.draft_orders)
      ? (state.data.draft_orders as ProcurementDraftOrder[])
      : [];

    const mergedDraftOrders = [...directDraftOrders, ...nestedDraftOrders];
    if (mergedDraftOrders.length > 0) {
      return mergedDraftOrders;
    }

    const directProposals = Array.isArray(state.purchase_order_proposals)
      ? state.purchase_order_proposals
      : [];
    const nestedProposals = Array.isArray(state.data?.purchase_order_proposals)
      ? state.data.purchase_order_proposals
      : [];

    return [...directProposals, ...nestedProposals].map((proposal) => ({
      supplier_id: 1,
      supplier_name: "Spotify Market Suggestion",
      source_type: "new_releases",
      order_path: "new_releases",
      total_amount: 0,
      market_popularity_score:
        typeof proposal.market_popularity_score === "number"
          ? proposal.market_popularity_score
          : undefined,
      ai_recommendation:
        "Inkoop gebaseerd op nieuwe release detectie.",
      items: [{
        product_id: proposal.product_id,
        product_name: proposal.product_name,
        quantity: proposal.quantity,
        unit_price: 0,
        source_type: "new_releases",
        order_path: "new_releases",
      }],
    } as ProcurementDraftOrder));
  }, [state]);

  const salesVelocityForecasts = useMemo(() => {
    const forecasts = state.data?.sales_velocity_forecasts;
    if (Array.isArray(forecasts) && forecasts.length > 0) {
      return forecasts;
    }
    return bootstrapSalesVelocityForecasts;
  }, [state.data, bootstrapSalesVelocityForecasts]);

  const supplierOffers = useMemo(() => {
    const offers = state.supplier_offers;
    if (Array.isArray(offers) && offers.length > 0) {
      return offers;
    }
    return bootstrapSupplierOffers;
  }, [state.supplier_offers, bootstrapSupplierOffers]);

  const visiblePendingCheckpoints = useMemo(() => {
    return [...pendingCheckpoints]
      .sort((a, b) => {
        const aTs = new Date(a.updated_at || a.approval_requested_at || 0).getTime();
        const bTs = new Date(b.updated_at || b.approval_requested_at || 0).getTime();
        return bTs - aTs;
      })
      .slice(0, 5);
  }, [pendingCheckpoints]);

  useConfigureSuggestions({
    available: "always",
    suggestions: [
      {
        title: "Start workflow",
        message: "Start de workflow en laad de eerstvolgende open checkpoint.",
      },
      {
        title: "Check voorraad",
        message: "Geef een kort overzicht van de huidige voorraadmeldingen en risico's.",
      },
      {
        title: "Sales status",
        message: "Vat de sales velocity alerts samen en geef een korte prioriteit.",
      },
      {
        title: "Supplier advies",
        message: "Welke leverancier-opties zijn nu het meest kansrijk en waarom?",
      },
    ],
  });


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
            <span>Leveranciersaanbiedingen</span>
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
          <details>
            <summary className="panel-summary">
              <span>Openstaande Checkpoints</span>

            </summary>

            <p style={{ marginBottom: "1rem" }}>
              Klik per checkpoint voor details en acties.
            </p>

            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", alignItems: "center", flexWrap: "wrap" }}>
              <button className="btn btn-soft" onClick={fetchPendingCheckpoints}>
                Vernieuwen
              </button>
              {pendingLoading && <span>Bezig met laden...</span>}

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

            {visiblePendingCheckpoints.length === 0 ? (
              <p>Geen openstaande checkpoints gevonden.</p>
            ) : (
              <div style={{ display: "grid", gap: "0.8rem" }}>
                {visiblePendingCheckpoints.map((item, idx) => (
                  (() => {
                    const checkpointOrders = (item.draft_orders || []) as ProcurementDraftOrder[];
                    const newReleaseCount = checkpointOrders.filter((order) => classifyDraftOrder(order) === "New Release").length;
                    const reorderCount = checkpointOrders.length - newReleaseCount;

                    return (
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
                        <span className="summary-chip" style={{ backgroundColor: "#fef3c7", color: "#7a4f01" }}>{newReleaseCount} New Release</span>
                        <span className="summary-chip" style={{ backgroundColor: "#e0e7ff", color: "#1d4ed8" }}>{reorderCount} Reorder</span>
                        <span className="summary-chip">{formatRelativeTime(item.updated_at || item.approval_requested_at)}</span>
                      </span>
                    </summary>

                    <div className="checkpoint-body">
                      <div style={{ color: "#475467", fontSize: "0.9rem" }}>
                        Technisch ID: {item.thread_id}
                      </div>
                      <div style={{ marginTop: "0.45rem", color: "#1f2937" }}>{item.message || "Geen extra bericht"}</div>

                      {/* Voorstel duplicatie verwijderd, alleen goedkeuring vereist-formulier blijft */}

                      <CheckpointActionPanel
                        checkpoint={item}
                        onSubmitDecision={(approvedIndices, rejectionReasonsByIndex) =>
                          submitActiveThreadDecision(approvedIndices, rejectionReasonsByIndex, item.thread_id)
                        }
                        isLoading={checkpointLoadId === item.thread_id}
                      />
                    </div>
                  </details>
                    );
                  })()
                ))}
              </div>
            )}
          </details>
        </section>

        {/* Show Draft Orders panel from create_purchase_order onward */}
        {(state.awaiting_human_approval || 
          state.step === "create_purchase_order" || 
          state.step === "human_approval" ||
          state.status === "awaiting_approval" ||
          state.status === "awaiting_human_approval")
          && activeDraftOrders.length > 0 && (
          <CheckpointActionPanel
            state={{ ...state, draft_orders: activeDraftOrders }}
            agent={agent}
            onSubmitDecision={activeThreadId ? submitActiveThreadDecision : undefined}
          />
        )}

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Voorraad Meldingen</span>
              <span className="summary-chip">{(state.inventory_alerts || []).length}</span>
            </summary>

            {(state.inventory_alerts || []).length === 0 ? (
              <p style={{ marginTop: "0.8rem" }}>Geen meldingen</p>
            ) : (
              <div className="info-card-grid" style={{ marginTop: "0.8rem" }}>
                {(state.inventory_alerts || []).map((alert, idx) => {
                  const level = classifyAlertLevel(alert);
                  return (
                    <article key={`${alert}-${idx}`} className={`info-card inventory-${level}`}>
                      <div className="info-card-head">
                        <span className="info-card-title">Melding {idx + 1}</span>
                        <span
                          className={`summary-chip ${
                            level === "high"
                              ? "summary-chip-danger"
                              : level === "medium"
                                ? "summary-chip-warning"
                                : "summary-chip-green"
                          }`}
                        >
                          {level === "high" ? "Kritiek" : level === "medium" ? "Waarschuwing" : "Info"}
                        </span>
                      </div>
                      <p className="info-card-text">{alert}</p>
                    </article>
                  );
                })}
              </div>
            )}
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Sales </span>
              <span className="summary-chip">{salesVelocityForecasts.length}</span>
            </summary>

            <div className="alert-chip-row" style={{ marginTop: "0.8rem" }}>
              {(state.sales_velocity_alerts || []).length === 0 && (
                <span className="summary-chip summary-chip-green">Geen dringende meldingen</span>
              )}
              {(state.sales_velocity_alerts || []).map((alert, idx) => (
                <span key={`velocity-alert-${idx}`} className="summary-chip summary-chip-warning">
                  {alert}
                </span>
              ))}
            </div>

            {salesVelocityForecasts.length === 0 ? (
              <p style={{ marginTop: "0.9rem" }}>Nog geen sales data</p>
            ) : (
              <div className="info-card-grid info-card-grid-3" style={{ marginTop: "0.9rem" }}>
                {salesVelocityForecasts.map((forecast: SalesVelocityForecast, idx: number) => (
                  <article key={`velocity-${forecast.product_id ?? idx}`} className="info-card">
                    <div className="info-card-head">
                      <span className="info-card-title">{forecast.product_name || forecast.product_id || "Onbekend product"}</span>
                      <span className="summary-chip summary-chip-blue">
                        {typeof forecast.velocity_per_day === "number"
                          ? `${forecast.velocity_per_day.toFixed(2)} / dag`
                          : "- / dag"}
                      </span>
                    </div>

                    <div className="metric-pair-grid">
                      <div>
                        <small>Stockout datum</small>
                        <strong>{forecast.predicted_stockout_date || "-"}</strong>
                      </div>
                      <div>
                        <small>Reorder basis</small>
                        <strong>{forecast.reorder_basis || "-"}</strong>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span className="checkpoint-title">Leveranciers</span>
              <span className="summary-chip summary-chip-blue">{supplierOffers.length}</span>
            </summary>

            {supplierOffers.length === 0 ? (
              <p style={{ marginTop: "0.8rem" }}>Nog geen offers</p>
            ) : (
              <div className="info-card-grid info-card-grid-3" style={{ marginTop: "0.85rem" }}>
                {supplierOffers.map((offer, idx) => (
                  <article key={`offer-${idx}`} className="info-card">
                    <div className="info-card-head">
                      <span className="info-card-title">{offer.supplier_name || offer.supplier_id || "Onbekende leverancier"}</span>
                      <span className="summary-chip summary-chip-blue">
                        {typeof offer.reliability_score === "number"
                          ? `Score ${offer.reliability_score.toFixed(2)}`
                          : "Score -"}
                      </span>
                    </div>

                    <p className="info-card-text">{offer.notes || "Geen aanvullende notities"}</p>

                    <div className="metric-pair-grid">
                      <div>
                        <small>Levertijd</small>
                        <strong>
                          {typeof offer.lead_time_days === "number"
                            ? `${offer.lead_time_days} dagen`
                            : "-"}
                        </strong>
                      </div>
                      <div>
                        <small>Supplier ID</small>
                        <strong>{offer.supplier_id ?? "-"}</strong>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </details>
        </section>

        <section className="panel">
          <details>
            <summary className="panel-summary">
              <span>Goedgekeurde bestellingen</span>
              <span className="summary-chip">
                {proposalHistory.length + activeDraftOrders.length + bootstrapApprovedOrders.length}
              </span>
            </summary>

            {proposalHistory.length === 0 && activeDraftOrders.length === 0 && bootstrapApprovedOrders.length === 0 && <p>Nog geen voorstellen in history</p>}

            {bootstrapApprovedOrders.length > 0 && (
              <div className="info-card-grid info-card-grid-2" style={{ marginTop: "0.85rem", marginBottom: "1rem" }}>
                {bootstrapApprovedOrders.map((order, idx) => (
                  <article key={`bootstrap-approved-${order.order_id ?? idx}`} className="info-card">
                    <div className="info-card-head">
                      <span className="info-card-title">
                        Bestelling #{order.order_id ?? "-"}
                      </span>
                      <span className="summary-chip summary-chip-green">{toFriendlyLabel(order.status, 18)}</span>
                    </div>

                    <p className="info-card-text">Leverancier: {order.supplier_name || "Onbekende leverancier"}</p>

                    <div className="metric-pair-grid">
                      <div>
                        <small>Totaal</small>
                        <strong>{formatCurrency(order.total_amount)}</strong>
                      </div>
                      <div>
                        <small>Order datum</small>
                        <strong>{formatRelativeTime(order.order_date)}</strong>
                      </div>
                    </div>

                    <div style={{ marginTop: "0.55rem" }}>
                      <small style={{ display: "block", color: "#607089", marginBottom: "0.22rem" }}>
                        Albums in bestelling
                      </small>
                      <div className="item-pill-row">
                        {(order.album_names || []).length === 0 && (
                          <span className="item-pill">Geen albumdetails</span>
                        )}
                        {(order.album_names || []).map((album, albumIdx) => (
                          <span key={`approved-order-${order.order_id ?? idx}-album-${albumIdx}`} className="item-pill">
                            {album}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div style={{ marginTop: "0.45rem", color: "#344054", fontSize: "0.88rem" }}>
                      Goedgekeurd door: {order.approved_by || "-"}
                    </div>
                  </article>
                ))}
              </div>
            )}

            {proposalHistory.length > 0 && (
              <div className="info-card-grid info-card-grid-2" style={{ marginTop: "0.8rem", marginBottom: "1rem" }}>
                {proposalHistory.map((entry, idx) => (
                  <article key={`history-thread-${entry.thread_id}-${idx}`} className="info-card">
                    <div className="info-card-head">
                      <span className="info-card-title">Thread {entry.thread_id}</span>
                      <span className={`summary-chip ${entry.resolved_decision === "approved" ? "summary-chip-green" : "summary-chip-danger"}`}>
                        {entry.resolved_decision === "approved" ? "Goedgekeurd" : "Afgewezen"}
                      </span>
                    </div>

                    <div className="alert-chip-row" style={{ marginBottom: "0.55rem" }}>
                      <span className="summary-chip summary-chip-blue">{entry.draft_orders_count} orders</span>
                      <span className="summary-chip">{formatRelativeTime(entry.resolved_at)}</span>
                    </div>

                    <div style={{ display: "grid", gap: "0.55rem" }}>
                      {(entry.draft_orders || []).length === 0 && <p>Geen orderdetails beschikbaar</p>}
                      {(entry.draft_orders || []).map((order, orderIdx) => (
                        <div key={`history-order-${entry.thread_id}-${orderIdx}`} className="nested-order-card">
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
                          <div className="item-pill-row" style={{ marginTop: "0.5rem" }}>
                            {(order.items || []).length === 0 && <span className="item-pill">Geen items</span>}
                            {(order.items || []).map((item, itemIdx) => (
                              <span key={`history-order-${entry.thread_id}-${orderIdx}-item-${itemIdx}`} className="item-pill">
                                {item.product_name || item.product_id || "Onbekend product"} x{item.quantity ?? 0} @ {formatCurrency(item.unit_price)}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            )}

            <div className="info-card-grid info-card-grid-2" style={{ marginTop: "0.8rem" }}>
              {activeDraftOrders.map((order: ProcurementDraftOrder, idx) => (
                <article key={`draft-${idx}`} className="info-card">
                  <div className="info-card-head">
                    <span className="info-card-title">Actief voorstel: {order.supplier_name || `Leverancier ${idx + 1}`}</span>
                    <span className="summary-chip">
                      {classifyDraftOrder(order)}
                    </span>
                  </div>

                  <div className="alert-chip-row" style={{ marginBottom: "0.5rem" }}>
                    <span className="summary-chip summary-chip-blue">
                      {formatCurrency(
                        typeof order.total_amount === "number"
                          ? order.total_amount
                          : (order.items || []).reduce((acc, item) => acc + (item.quantity ?? 0) * (item.unit_price ?? 0), 0)
                      )}
                    </span>
                    <span className="summary-chip">{(order.items || []).length} items</span>
                  </div>

                  {order.ai_recommendation && (
                    <div style={{ marginTop: "0.2rem", color: "#344054", fontSize: "0.92rem" }}>
                      Reden voorstel: {order.ai_recommendation}
                    </div>
                  )}

                  <div className="item-pill-row" style={{ marginTop: "0.5rem" }}>
                    {(order.items || []).length === 0 && <span className="item-pill">Geen items</span>}
                    {(order.items || []).map((item, itemIdx) => (
                      <span key={`draft-${idx}-item-${itemIdx}`} className="item-pill">
                        {item.product_name || item.product_id || "Onbekend product"} x{item.quantity ?? 0} @ {formatCurrency(item.unit_price)}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </details>
        </section>
      </div>

      <aside className="vinyl-chat-panel">
        <CopilotChat
          agentId={AGENT_ID}
          className="vinyl-chat-shell"
          labels={{
            chatInputPlaceholder: "Typ je vraag of kies een suggestie...",
            welcomeMessageText: "Vinyl Inkoop Assistent",
          }}
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

