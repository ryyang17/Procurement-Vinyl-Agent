"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  CopilotKit,
  CopilotSidebar,
  UseAgentUpdate,
  useAgent,
  useCopilotKit,
  useConfigureSuggestions,
} from "@copilotkit/react-core/v2";

import "@copilotkit/react-core/v2/styles.css";
import "./style.css";
import {
  INITIAL_AGENT_STATE,
  DbOrderHistoryEntry,
  DraftOrder,
  ProcurementAgentState,
  SupplierSelection,
  SupplierOffer,
  formatCurrency,
} from "./agent";

const AGENT_ID = "procurement_agent";

type DashboardViewState = {
  inventoryAlerts: string[];
  supplierOffers: SupplierOffer[];
  supplierMatches: SupplierSelection[];
  draftOrders: DraftOrder[];
  newReleaseAlerts: string[];
  pendingProposals: string[];
  createdOrders: { order_id?: number; supplier_name?: string; total_amount?: number }[];
  orderHistory: DbOrderHistoryEntry[];
};

type AgentStateBridge = {
  setState: (state: ProcurementAgentState) => void;
  state?: unknown;
};

type SubmitStateFn = (state: ProcurementAgentState) => Promise<void>;

type SavedPendingProposal = {
  id: string;
  thread_id: string;
  saved_at: string;
  draft_orders: DraftOrder[];
  snapshot: ProcurementAgentState;
};

const PENDING_PROPOSALS_STORAGE_KEY = "vinyl_open_pending_proposals_v1";

function createThreadId(): string {
  const rand = Math.random().toString(36).slice(2, 10).toUpperCase();
  return `ui-${Date.now()}-${rand}`;
}

function sourceTagLabel(sourceType?: string): string {
  switch (sourceType) {
    case "new_release_spotify":
      return "New Release (Spotify)";
    case "existing_inventory_new_release":
      return "New Release (Bestaande DB)";
    case "inventory_low_stock":
      return "Inventory";
    default:
      return sourceType ? sourceType : "Onbekende bron";
  }
}

function getOrderPath(order: DraftOrder): string | undefined {
  return (order as DraftOrder & { order_path?: string }).order_path;
}

function isSupplierOrder(order: DraftOrder): boolean {
  const orderPath = getOrderPath(order);
  return orderPath === "suppliers" || order.source_type === "inventory_low_stock";
}

function isNewReleaseOrder(order: DraftOrder): boolean {
  const orderPath = getOrderPath(order);
  return (
    orderPath === "new_releases" ||
    order.source_type === "new_release_spotify" ||
    order.source_type === "existing_inventory_new_release"
  );
}

function buildDashboardViewState(state: ProcurementAgentState): DashboardViewState {
  const reorderProposals = state.data?.reorder_proposals ?? [];
  const supplierSelections = state.data?.supplier_selections ?? [];
  const draftOrders = state.data?.draft_orders ?? state.draft_orders ?? [];
  const purchaseOrderProposals =
    state.data?.purchase_order_proposals ?? state.purchase_order_proposals ?? [];
  const createdOrders = state.data?.created_orders ?? [];
  const orderHistory = state.data?.order_history ?? [];

  const inventoryAlerts = reorderProposals.map(
    (p) =>
      `${p.product_name ?? p.product_code ?? "Onbekend"} [${p.category ?? "Unknown"}] - ${p.current_qty ?? 0} op voorraad (min ${p.min_threshold ?? 0}), voorstel ${p.reorder_qty ?? 0} (${sourceTagLabel(p.source_type)})`,
  );

  const supplierOfferMap = new Map<string, SupplierOffer>();
  supplierSelections.forEach((selection) => {
    (selection.all_options ?? []).forEach((option) => {
      const key = `${selection.product_id ?? selection.product_name}-${option.supplier_id ?? option.supplier_name}`;
      if (!supplierOfferMap.has(key)) {
        supplierOfferMap.set(key, {
          ...option,
          product_name: selection.product_name,
          category: selection.category,
          source_type: selection.source_type,
        });
      }
    });
  });
  const supplierOffers = Array.from(supplierOfferMap.values());

  const newReleaseAlerts = (state.new_releases ?? []).map(
    (release) =>
      `${release.title ?? "Onbekende release"} - ${release.artist ?? "Unknown artist"} [${release.category ?? release.genre ?? "Unknown"}] (${sourceTagLabel(release.source_type)})`,
  );

  const pendingProposals = purchaseOrderProposals.map(
    (proposal) =>
      `${proposal.product_name ?? "Onbekend product"} [${proposal.category ?? "Unknown"}] x ${proposal.quantity ?? 0} (${sourceTagLabel(proposal.source_type)})`,
  );

  return {
    inventoryAlerts,
    supplierOffers,
    supplierMatches: supplierSelections,
    draftOrders,
    newReleaseAlerts,
    pendingProposals,
    createdOrders,
    orderHistory,
  };
}

/**
 * Component voor pad selectie: user kiest tussen leveranciers of nieuwe releases
 */
function PathSelectionPanel({
  state,
  submitState,
}: {
  state: ProcurementAgentState;
  submitState: SubmitStateFn;
}) {
  const hasInventoryAlerts = (state.inventory_alerts?.length ?? 0) > 0;

  const handlePathChoice = (choice: "path_1_suppliers" | "path_2_new_releases") => {
    console.log(`🔧 DEBUG: handlePathChoice called with choice: ${choice}`);
    console.log(`   Current state:`, {
      step: state.step,
      status: state.status,
      awaiting_path_selection: state.awaiting_path_selection,
      path_choice: state.path_choice
    });
    
    const newState = {
      ...state,
      path_choice: choice,
      awaiting_path_selection: false,
      step: "path_selected",  // Clear awaiting_human_input
      status: "processing",
      message: `Pad geselecteerd: ${choice === "path_1_suppliers" ? "Leveranciers zoeken" : "Nieuwe releases checken"}`
    };
    
    console.log(`   New state:`, newState);
    void submitState(newState);
  };

  return (
    <section className="panel" style={{ backgroundColor: "#f0f8ff", borderColor: "#0066cc", border: "2px solid #0066cc" }}>
      <h2>🛣️ Selecteer Werkstroom</h2>

      {/* Voorraadinformatie */}
      <div style={{
        backgroundColor: "#e8f4f8",
        padding: "1rem",
        borderRadius: "8px",
        marginBottom: "1rem",
        borderLeft: "4px solid #0066cc"
      }}>
        <strong>📦 Voorraadinformatie:</strong>
        {hasInventoryAlerts ? (
          <p style={{ margin: "0.5rem 0 0 0", color: "#d9534f" }}>
            ⚠️ {state.inventory_alerts?.length} producten hebben voorraden onder minimum
          </p>
        ) : (
          <p style={{ margin: "0.5rem 0 0 0", color: "#5cb85c" }}>
            ✅ Alle voorraden zijn boven minimum. Geen actie nodig, maar je kunt nog:
          </p>
        )}
      </div>

      <p style={{ marginBottom: "1.5rem", fontWeight: "500" }}>
        Kies wat je wilt doen:
      </p>

      <div style={{ display: "flex", gap: "1rem", marginTop: "1rem", flexDirection: "column" }}>
        {/* Pad 1: Leveranciers */}
        <button
          onClick={() => handlePathChoice("path_1_suppliers")}
          style={{
            padding: "1.5rem",
            backgroundColor: "#0066cc",
            color: "white",
            border: "none",
            borderRadius: "8px",
            cursor: "pointer",
            fontSize: "1rem",
            fontWeight: "bold",
            textAlign: "left",
            transition: "all 0.3s ease",
          }}
          onMouseEnter={(e) => {
            (e.target as HTMLButtonElement).style.backgroundColor = "#0052a3";
            (e.target as HTMLButtonElement).style.boxShadow = "0 4px 8px rgba(0, 102, 204, 0.3)";
          }}
          onMouseLeave={(e) => {
            (e.target as HTMLButtonElement).style.backgroundColor = "#0066cc";
            (e.target as HTMLButtonElement).style.boxShadow = "none";
          }}
        >
          <div style={{ fontSize: "1.2rem", marginBottom: "0.5rem" }}>
            🏭 Pad 1: Leveranciers Controleren
          </div>
          <div style={{ fontSize: "0.9rem", opacity: 0.9 }}>
            {hasInventoryAlerts
              ? "Zoek best mogelijke leveranciers voor producten met lage voorraad"
              : "Screen leveranciers op prijs, levertijd en betrouwbaarheid voor toekomstige aankopen"
            }
          </div>
        </button>

        {/* Pad 2: Nieuwe Releases */}
        <button
          onClick={() => handlePathChoice("path_2_new_releases")}
          style={{
            padding: "1.5rem",
            backgroundColor: "#00aa00",
            color: "white",
            border: "none",
            borderRadius: "8px",
            cursor: "pointer",
            fontSize: "1rem",
            fontWeight: "bold",
            textAlign: "left",
            transition: "all 0.3s ease",
          }}
          onMouseEnter={(e) => {
            (e.target as HTMLButtonElement).style.backgroundColor = "#008800";
            (e.target as HTMLButtonElement).style.boxShadow = "0 4px 8px rgba(0, 170, 0, 0.3)";
          }}
          onMouseLeave={(e) => {
            (e.target as HTMLButtonElement).style.backgroundColor = "#00aa00";
            (e.target as HTMLButtonElement).style.boxShadow = "none";
          }}
        >
          <div style={{ fontSize: "1.2rem", marginBottom: "0.5rem" }}>
            🎵 Pad 2: Nieuwe Releases Checken
          </div>
          <div style={{ fontSize: "0.9rem", opacity: 0.9 }}>
            Controleer nieuwe vinyl releases en bepaal of inkoop nodig is
          </div>
        </button>
      </div>

      <div style={{
        marginTop: "1.5rem",
        padding: "1rem",
        backgroundColor: "#fff3cd",
        borderRadius: "8px",
        borderLeft: "4px solid #ffc107",
        fontSize: "0.9rem"
      }}>
        <strong>💡 Tip:</strong> Je kunt beide paden achtereenvolgens uitvoeren. Beide leiden tot inkoopbeslissingen die goedkeuring nodig hebben.
      </div>
    </section>
  );
}

/**
 * Component voor goedkeuringspaneel: user keurt orders goed/af
 */
function ApprovalPanel({
  state,
  agent,
  submitState,
}: {
  state: ProcurementAgentState;
  agent: AgentStateBridge;
  submitState: SubmitStateFn;
}) {
  const [localApprovals, setLocalApprovals] = useState<Record<number, boolean>>({});
  const [localRejectionReasons, setLocalRejectionReasons] = useState<Record<number, string>>({});

  const draftOrders = state.data?.draft_orders ?? state.draft_orders ?? [];

  const handleToggleApproval = (index: number) => {
    setLocalApprovals((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
    // ...existing code...
    if (localApprovals[index]) {
      setLocalRejectionReasons((prev) => {
        const newReasons = { ...prev };
        delete newReasons[index];
        return newReasons;
      });
    }
  };

  const handleRejectionReasonChange = (index: number, reason: string) => {
    setLocalRejectionReasons((prev) => ({
      ...prev,
      [index]: reason,
    }));
  };

  const handleSubmitApproval = () => {
    const approvedIndices = Object.entries(localApprovals)
      .filter(([, approved]) => approved)
      .map(([idx]) => parseInt(idx));
    const hasRejections = Object.keys(localRejectionReasons).length > 0;

    void submitState({
      ...state,
      approval_order_indices: approvedIndices,
      rejection_reasons_by_index: localRejectionReasons,
      awaiting_human_approval: false,
      step: "processing_approval",
      status: "processing_approval",
      approval_decision: approvedIndices.length > 0 ? "approved" : hasRejections ? "rejected" : "pending",
      approved_by: "manager",
    });
  };

  // ...existing code...
  if (draftOrders.length === 0) {
    return (
      <section className="panel" style={{ backgroundColor: "#f0fff0", borderColor: "#5cb85c", border: "2px solid #5cb85c" }}>
        <h2>✅ Geen Orders Nodig</h2>
        <p style={{ fontSize: "1.1rem", color: "#5cb85c" }}>
          Na de analyse zijn er geen inkooporders nodig. Alles is in orde!
        </p>
        <button
          onClick={() => {
            agent.setState({
              ...state,
              awaiting_human_approval: false,
              approval_order_indices: [],
              rejection_reasons_by_index: {},
              step: "complete",
              status: "ok"
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
      <h2>✅ Goedkeuring Bestellingen</h2>
      <p>{draftOrders.length} bestellingen wachten op goedkeuring:</p>

      <div style={{ marginTop: "1rem" }}>
        {draftOrders.map((order, idx) => (
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
                <strong>{order.supplier_name || "Leverancier " + (idx + 1)}</strong>
                <div style={{ fontSize: "0.9rem", color: "#666" }}>
                  {(order.items || []).length} item(s) • levertijd {order.lead_time_days ?? "-"} dagen • kwaliteit {order.quality_rating ?? "-"}
                </div>
                <div style={{ marginTop: "0.4rem", fontSize: "0.9rem", color: "#444" }}>
                  {(order.items || []).map((item, itemIdx) => (
                    <div key={`order-${idx}-item-${itemIdx}`}>
                      • {item.product_name || "Onbekend product"} x {item.quantity ?? 0} @ {formatCurrency(item.unit_price)}
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ textAlign: "right", fontWeight: "bold" }}>
                {formatCurrency(order.total_amount)}
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

      <button
        onClick={handleSubmitApproval}
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
        }}
      >
        Goedkeuringen Indienen
      </button>
    </section>
  );
}

function Dashboard() {
  const { copilotkit } = useCopilotKit();
  const { agent } = useAgent({
    agentId: AGENT_ID,
    updates: [UseAgentUpdate.OnStateChanged, UseAgentUpdate.OnRunStatusChanged],
  });

  const submitStateAndRun = React.useCallback(
    async (nextState: ProcurementAgentState) => {
      agent.setState(nextState);
      try {
        await copilotkit.runAgent({ agent });
      } catch (error) {
        console.error("Failed to run agent after state update", error);
      }
    },
    [agent, copilotkit],
  );

  useConfigureSuggestions({
    suggestions: [
      {
        title: "Controleer voorraadtekorten",
        message: "Voer een dagelijkse voorraadcontrole uit en toon tekorten.",
      },
      {
        title: "Vergelijk leveranciers",
        message: "Vergelijk leveranciers op prijs, levertijd en betrouwbaarheid.",
      },
      {
        title: "Check openstaande conceptbestellingen",
        message: "Toon openstaande conceptbestellingen en hun status.",
      },
      {
        title: "Vraag goedkeuring",
        message: "Bereid human approval voor met duidelijke motivatie.",
      },
      {
        title: "Toon order geschiedenis",
        message: "Laat de ordergeschiedenis uit de database zien.",
      },
    ],
    available: "always",
  });

  const state = (agent.state as ProcurementAgentState) || INITIAL_AGENT_STATE;
  const viewState = useMemo(() => buildDashboardViewState(state), [state]);
  const [sessionThreadId, setSessionThreadId] = useState<string>("");
  const [savedPendingProposals, setSavedPendingProposals] = useState<SavedPendingProposal[]>([]);
  const [storageLoaded, setStorageLoaded] = useState(false);

  useEffect(() => {
    setSessionThreadId(createThreadId());
  }, []);

  useEffect(() => {
    const raw = window.localStorage.getItem(PENDING_PROPOSALS_STORAGE_KEY);
    if (!raw) {
      setStorageLoaded(true);
      return;
    }

    try {
      const parsed = JSON.parse(raw) as SavedPendingProposal[];
      setSavedPendingProposals(Array.isArray(parsed) ? parsed : []);
    } catch {
      setSavedPendingProposals([]);
    } finally {
      setStorageLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (!agent.state) {
      agent.setState({
        ...INITIAL_AGENT_STATE,
        thread_id: createThreadId(),
      });
    }
  }, [agent]);

  const effectiveThreadId = state.thread_id?.trim() || sessionThreadId;

  const effectivePendingProposals = useMemo(() => {
    const draftOrders = state.data?.draft_orders ?? state.draft_orders ?? [];
    const hasDraftOrders = draftOrders.length > 0;
    const isAwaitingApproval =
      state.awaiting_human_approval ||
      state.status === "awaiting_approval" ||
      state.step === "awaiting_human_input";
    const isCompleted = state.status === "orders_placed" || state.step === "complete";
    let next = savedPendingProposals;

    if (isAwaitingApproval && hasDraftOrders) {
      const proposal: SavedPendingProposal = {
        id: effectiveThreadId,
        thread_id: effectiveThreadId,
        saved_at: new Date().toISOString(),
        draft_orders: draftOrders,
        snapshot: {
          ...state,
          thread_id: effectiveThreadId,
          awaiting_human_approval: true,
          status: "awaiting_approval",
          step: "awaiting_human_input",
        },
      };

      const withoutCurrent = savedPendingProposals.filter((item) => item.thread_id !== effectiveThreadId);
      next = [proposal, ...withoutCurrent].slice(0, 25);
    } else if (isCompleted) {
      next = savedPendingProposals.filter((item) => item.thread_id !== effectiveThreadId);
    }

    return next;
  }, [effectiveThreadId, savedPendingProposals, state]);

  useEffect(() => {
    if (!storageLoaded) {
      return;
    }
    window.localStorage.setItem(PENDING_PROPOSALS_STORAGE_KEY, JSON.stringify(effectivePendingProposals));
  }, [effectivePendingProposals, storageLoaded]);

  const handleResumePendingProposal = (proposal: SavedPendingProposal) => {
    agent.setState({
      ...proposal.snapshot,
      thread_id: proposal.thread_id,
      awaiting_human_approval: true,
      status: "awaiting_approval",
      step: "awaiting_human_input",
    });
  };

  const handleDeletePendingProposal = (threadId: string) => {
    setSavedPendingProposals((prev) => {
      const next = prev.filter((item) => item.thread_id !== threadId);
      window.localStorage.setItem(PENDING_PROPOSALS_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  };

  const kpis = useMemo(() => {
    const alerts = viewState.inventoryAlerts.length;
    const offers = viewState.supplierOffers.length;
    const draftOrders = viewState.draftOrders.length;
    const approvals = viewState.createdOrders.length;
    return { alerts, offers, draftOrders, approvals };
  }, [viewState]);

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

        {/* Workflow Interaction Panels */}
        {(state.awaiting_path_selection ||
          (state.status === "awaiting_path_selection" && !state.path_choice) ||
          (state.step === "awaiting_human_input" && state.status === "awaiting_path_selection")) && (
          <PathSelectionPanel
            state={{ ...state, inventory_alerts: viewState.inventoryAlerts }}
            submitState={submitStateAndRun}
          />
        )}

        {(state.awaiting_human_approval ||
          state.status === "awaiting_approval" ||
          state.step === "awaiting_human_input" && viewState.draftOrders.length > 0) && (
          <ApprovalPanel state={state} agent={agent} submitState={submitStateAndRun} />
        )}

        <section className="panel">
          <h2>Workflow Status</h2>
          <div className="status-row">
            <div>
              <label>Stap</label>
              <p>{state.step || "-"}</p>
            </div>
            <div>
              <label>Status</label>
              <p>{state.status || "-"}</p>
            </div>
            <div>
              <label>Volgende Actie</label>
              <p>{state.next_action || "-"}</p>
            </div>
            <div>
              <label>Path Choice</label>
              <p>{state.path_choice || "Geen"}</p>
            </div>
            <div>
              <label>Awaiting Path</label>
              <p>{state.awaiting_path_selection ? "Ja" : "Nee"}</p>
            </div>
            <div>
              <label>Approval</label>
              <p>{state.approval_decision || "-"}</p>
            </div>
          </div>
          <div className="summary-box">
            {state.summary || state.message || "Nog geen samenvatting beschikbaar."}
          </div>

          {/* Debug informatie */}
          <details style={{ marginTop: "1rem", fontSize: "0.8rem", background: "#f5f5f5", padding: "0.5rem", borderRadius: "4px" }}>
            <summary style={{ cursor: "pointer", fontWeight: "bold" }}>🔧 Debug State Info</summary>
            <pre style={{ margin: "0.5rem 0", overflow: "auto", maxHeight: "200px", fontSize: "0.7rem", background: "white", padding: "0.5rem", border: "1px solid #ddd" }}>
              {JSON.stringify({
                awaiting_path_selection: state.awaiting_path_selection,
                path_choice: state.path_choice,
                step: state.step,
                status: state.status,
                awaiting_human_approval: state.awaiting_human_approval,
                draftOrdersCount: viewState.draftOrders.length,
                inventoryAlertsCount: viewState.inventoryAlerts.length
              }, null, 2)}
            </pre>
          </details>
        </section>

        <section className="panel" style={{ backgroundColor: "#e8f5e8", borderColor: "#28a745", border: "3px solid #28a745" }}>
          <h2>🚀 Directe Workflow Keuze</h2>
          <p><strong>Klik op een knop om direct te beginnen:</strong></p>

          <div style={{ display: "flex", gap: "1rem", marginTop: "1rem", flexDirection: "column" }}>
            <button
              onClick={() => {
                void submitStateAndRun({
                  ...state,
                  awaiting_path_selection: true,
                  step: "awaiting_human_input",
                  status: "awaiting_path_selection",
                  message: "Handmatig gestart - selecteer een werkstroom",
                  path_choice: null
                });
              }}
              style={{
                padding: "1rem",
                backgroundColor: "#28a745",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "1rem",
                fontWeight: "bold",
              }}
            >
              🛣️ Start Pad Selectie
            </button>

            <button
              onClick={() => {
                console.log("🔧 DEBUG: Direct leveranciers zoeken button clicked");
                void submitStateAndRun({
                  ...state,
                  awaiting_path_selection: false,
                  path_choice: "path_1_suppliers",
                  step: "path_selected",
                  status: "processing",
                  message: "Direct naar leveranciers zoeken..."
                });
              }}
              style={{
                padding: "0.8rem",
                backgroundColor: "#007bff",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "0.9rem",
              }}
            >
              🏭 Direct Leveranciers Zoeken
            </button>

            <button
              onClick={() => {
                console.log("🔧 DEBUG: Direct nieuwe releases checken button clicked");
                void submitStateAndRun({
                  ...state,
                  awaiting_path_selection: false,
                  path_choice: "path_2_new_releases",
                  step: "path_selected",
                  status: "processing",
                  message: "Direct naar nieuwe releases checken..."
                });
              }}
              style={{
                padding: "0.8rem",
                backgroundColor: "#6f42c1",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "0.9rem",
              }}
            >
              🎵 Direct Nieuwe Releases Checken
            </button>
          </div>
        </section>

        <section className="panel">
          <h2>Beste Supplier Match Per Record</h2>
          <ul className="list">
            {viewState.supplierMatches.length === 0 && <li>Nog geen supplier-matches</li>}
            {viewState.supplierMatches.map((match, idx) => (
              <li key={`match-${idx}`}>
                {match.product_name ?? "Onbekend product"} [{match.category ?? "Unknown"}] -
                Beste match: {match.selected_supplier?.supplier_name ?? "Onbekend"} ({sourceTagLabel(match.source_type)})
                {match.ai_recommendation_summary ? ` | ${match.ai_recommendation_summary}` : ""}
              </li>
            ))}
          </ul>
        </section>

        <section className="panel" style={{ backgroundColor: "#fff3e0", borderColor: "#ff9800", border: "2px solid #ff9800" }}>
          <h2>💾 Thread Memory Management</h2>
          <p><strong>Current Thread:</strong> {effectiveThreadId}</p>

          <div style={{ marginTop: "1rem", display: "flex", gap: "1rem", flexDirection: "column" }}>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button
                onClick={() => {
                  const newThreadId = createThreadId();
                  agent.setState({
                    ...INITIAL_AGENT_STATE,
                    thread_id: newThreadId,
                  });
                }}
                style={{
                  padding: "0.5rem 1rem",
                  backgroundColor: "#ff9800",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                }}
              >
                🆕 Nieuwe Thread
              </button>

              <button
                onClick={() => {
                  agent.setState({
                    ...state,
                    thread_id: effectiveThreadId,
                    awaiting_path_selection: false,
                    awaiting_human_approval: false,
                    step: "process_due_deliveries",
                    status: "pending",
                    message: "Thread gereset naar start workflow.",
                    path_choice: null,
                  });
                }}
                style={{
                  padding: "0.5rem 1rem",
                  backgroundColor: "#2196f3",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                }}
              >
                🔄 Reset Thread
              </button>

              <button
                onClick={() => {
                  const stateSnapshot = {
                    thread_id: effectiveThreadId,
                    timestamp: new Date().toISOString(),
                    state: state,
                    draft_orders: state.data?.draft_orders ?? [],
                    path_choice: state.path_choice,
                    step: state.step,
                    status: state.status
                  };
                  console.log("Thread State Snapshot:", stateSnapshot);
                  alert(`Thread snapshot logged to console. Thread: ${effectiveThreadId}`);
                }}
                style={{
                  padding: "0.5rem 1rem",
                  backgroundColor: "#9c27b0",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                }}
              >
                📊 Debug Snapshot
              </button>
            </div>
          </div>

          <div style={{ marginTop: "1rem", fontSize: "0.8rem", color: "#666" }}>
            💡 <strong>Tip:</strong> Elke thread houdt eigen state en workflow. Gebruik &quot;Hervat geselecteerd voorstel&quot; hieronder om tussen threads te switchen.
          </div>
        </section>

        <section className="panel">
          <h2>Openstaande Inkoopvoorstellen (Thread Memory)</h2>
          <p>{effectivePendingProposals.length} opgeslagen thread{effectivePendingProposals.length !== 1 ? 's' : ''}</p>
          <ul className="list">
            {effectivePendingProposals.length === 0 && <li>Geen opgeslagen openstaande voorstellen</li>}
            {effectivePendingProposals.map((proposal) => {
              const isCurrentThread = proposal.thread_id === effectiveThreadId;
              const hasSupplierOrders = proposal.draft_orders.some((order) => isSupplierOrder(order));
              const hasNewReleaseOrders = proposal.draft_orders.some((order) => isNewReleaseOrder(order));
              const pathIcon = hasSupplierOrders && hasNewReleaseOrders ? "🔀" : hasSupplierOrders ? "🏭" : hasNewReleaseOrders ? "🎵" : "📦";

              return (
                <li key={`saved-pending-${proposal.id}`} style={{
                  padding: "1rem",
                  backgroundColor: isCurrentThread ? "#e8f4fd" : "white",
                  border: isCurrentThread ? "2px solid #2196f3" : "1px solid #ddd",
                  borderRadius: "8px",
                  marginBottom: "0.5rem"
                }}>
                  <div style={{ fontWeight: "bold", marginBottom: "0.5rem" }}>
                    {pathIcon} Thread {proposal.thread_id} {isCurrentThread ? "(ACTIEF)" : ""}
                  </div>
                  <div style={{ fontSize: "0.9rem", color: "#666", marginBottom: "0.5rem" }}>
                    {proposal.draft_orders.length} conceptbestellingen • {proposal.saved_at.replace("T", " ").slice(0, 16)}

                  </div>
                  {proposal.draft_orders.length > 0 && (
                    <div style={{ fontSize: "0.8rem", color: "#888", marginBottom: "0.5rem" }}>
                      Orders: {proposal.draft_orders.map(order =>
                        `${order.supplier_name} (${(order.items || []).length} items)`
                      ).join(", ")}
                    </div>
                  )}
                  <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {!isCurrentThread && (
                      <button
                        onClick={() => handleResumePendingProposal(proposal)}
                        style={{
                          padding: "0.45rem 0.8rem",
                          border: "1px solid #1f6feb",
                          backgroundColor: "#1f6feb",
                          color: "white",
                          borderRadius: "6px",
                          cursor: "pointer",
                        }}
                      >
                        🔄 Switch naar deze Thread
                      </button>
                    )}
                    <button
                      onClick={() => handleDeletePendingProposal(proposal.thread_id)}
                      style={{
                        padding: "0.45rem 0.8rem",
                        border: "1px solid #dc3545",
                        backgroundColor: proposal.thread_id === effectiveThreadId ? "#dc3545" : "white",
                        color: proposal.thread_id === effectiveThreadId ? "white" : "#dc3545",
                        borderRadius: "6px",
                        cursor: "pointer",
                      }}
                    >
                      🗑️ Verwijder Thread
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="panel">
          <h2>Openstaande Inkoopvoorstellen</h2>
          <ul className="list">
            {viewState.pendingProposals.length === 0 && <li>Geen openstaande voorstellen</li>}
            {viewState.pendingProposals.map((proposal, idx) => (
              <li key={`proposal-${idx}`}>{proposal}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Voorraad Meldingen</h2>
          <ul className="list">
            {viewState.inventoryAlerts.length === 0 && <li>Geen meldingen</li>}
            {viewState.inventoryAlerts.map((alert, idx) => (
              <li key={`${alert}-${idx}`}>{alert}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Nieuwe Release Meldingen</h2>
          <ul className="list">
            {viewState.newReleaseAlerts.length === 0 && <li>Geen nieuwe releases gemeld</li>}
            {viewState.newReleaseAlerts.map((release, idx) => (
              <li key={`release-${idx}`}>{release}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Supplier Offers</h2>
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
                {viewState.supplierOffers.length === 0 && (
                  <tr>
                    <td colSpan={5}>Nog geen offers</td>
                  </tr>
                )}
                {viewState.supplierOffers.map((offer, idx) => (
                  <tr key={`offer-${idx}`}>
                    <td>{offer.supplier_name || offer.supplier_id || "-"}</td>
                    <td>{offer.product_name || "-"} [{offer.category || "Unknown"}]</td>
                    <td>{formatCurrency(offer.price_per_unit ?? offer.unit_price)}</td>
                    <td>
                      {typeof offer.lead_time_days === "number"
                        ? `${offer.lead_time_days} d`
                        : "-"}
                    </td>
                    <td>
                      {typeof offer.quality_rating === "number"
                        ? offer.quality_rating.toFixed(1)
                        : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <h2>Draft Orders (Met Path Separatie)</h2>

          {/* Supplier Orders */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ color: "#0066cc", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              🏭 Leveranciers Orders ({viewState.draftOrders.filter((order) => isSupplierOrder(order)).length})
            </h3>
            <ul className="list">
              {viewState.draftOrders.filter((order) => isSupplierOrder(order)).length === 0 && (
                <li style={{ fontStyle: "italic", color: "#666" }}>Geen leveranciers orders</li>
              )}
              {viewState.draftOrders
                .filter((order) => isSupplierOrder(order))
                .map((order, idx) => (
                  <li key={`supplier-draft-${idx}`} style={{ backgroundColor: "#f0f8ff", padding: "0.5rem", borderLeft: "4px solid #0066cc", marginBottom: "0.5rem" }}>
                    <strong>{order.supplier_name || "Onbekende leverancier"}</strong> - {formatCurrency(order.total_amount)} ({(order.items || []).length} items)
                    <div style={{ fontSize: "0.8rem", color: "#666", marginTop: "0.25rem" }}>
                      Bron: Voorraad tekorten • Pad: Leveranciers
                    </div>
                    {(order.items || []).length > 0 && (
                      <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                        {order.items?.map((item, itemIdx) => (
                          <div key={`supplier-item-${itemIdx}`} style={{ marginLeft: "1rem" }}>
                            • {item.product_name || "Onbekend"} [{item.category || "Unknown"}] x{item.quantity} @ {formatCurrency(item.unit_price)}
                          </div>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
            </ul>
          </div>

          {/* New Release Orders */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ color: "#00aa00", marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              🎵 Nieuwe Release Orders ({viewState.draftOrders.filter((order) => isNewReleaseOrder(order)).length})
            </h3>
            <ul className="list">
              {viewState.draftOrders.filter((order) => isNewReleaseOrder(order)).length === 0 && (
                <li style={{ fontStyle: "italic", color: "#666" }}>Geen nieuwe release orders</li>
              )}
              {viewState.draftOrders
                .filter((order) => isNewReleaseOrder(order))
                .map((order, idx) => (
                  <li key={`newrelease-draft-${idx}`} style={{ backgroundColor: "#f0fff0", padding: "0.5rem", borderLeft: "4px solid #00aa00", marginBottom: "0.5rem" }}>
                    <strong>{order.supplier_name || "Onbekende leverancier"}</strong> - {formatCurrency(order.total_amount)} ({(order.items || []).length} items)
                    <div style={{ fontSize: "0.8rem", color: "#666", marginTop: "0.25rem" }}>
                      Bron: {sourceTagLabel(order.source_type)} • Pad: Nieuwe Releases
                    </div>
                    {(order.items || []).length > 0 && (
                      <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                        {order.items?.map((item, itemIdx) => (
                          <div key={`newrelease-item-${itemIdx}`} style={{ marginLeft: "1rem" }}>
                            • {item.product_name || "Onbekend"} [{item.category || "Unknown"}] x{item.quantity} @ {formatCurrency(item.unit_price)}
                          </div>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
            </ul>
          </div>

          {/* Summary */}
          <div style={{ padding: "1rem", backgroundColor: "#f8f9fa", borderRadius: "8px", border: "1px solid #dee2e6" }}>
            <strong>📊 Totaal Overzicht:</strong>
            <div style={{ marginTop: "0.5rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div>
                🏭 Leveranciers: {viewState.draftOrders.filter((order) => isSupplierOrder(order)).length} orders
              </div>
              <div>
                🎵 Nieuwe Releases: {viewState.draftOrders.filter((order) => isNewReleaseOrder(order)).length} orders
              </div>
            </div>
            <div style={{ marginTop: "0.5rem", fontSize: "0.9rem", color: "#666" }}>
              Totaal waarde: {formatCurrency(viewState.draftOrders.reduce((sum, order) => sum + (order.total_amount || 0), 0))}
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>Order Geschiedenis</h2>
          <ul className="list">
            {viewState.orderHistory.length === 0 && <li>Nog geen orderhistorie beschikbaar</li>}
            {viewState.orderHistory.map((event, idx) => (
              <li key={`history-${idx}`}>
                {(event.order_date || "-").replace("T", " ").slice(0, 16)} - Order #{event.order_id ?? "-"}
                {event.supplier_name ? ` - ${event.supplier_name}` : ""}
                {event.status ? ` - status: ${event.status}` : ""}
                {typeof event.total_amount === "number" ? ` - ${formatCurrency(event.total_amount)}` : ""}
              </li>
            ))}
          </ul>
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

