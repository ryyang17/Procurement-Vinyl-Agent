"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  CopilotKit,
  CopilotSidebar,
  UseAgentUpdate,
  useAgent,
  useConfigureSuggestions,
} from "@copilotkit/react-core/v2";

import "@copilotkit/react-core/v2/styles.css";
import "./style.css";
import {
  INITIAL_AGENT_STATE,
  DecisionHistoryEntry,
  DraftOrder,
  ProcurementAgentState,
  SupplierOffer,
  formatCurrency,
} from "./agent";

const AGENT_ID = "procurement_agent";

type DashboardViewState = {
  inventoryAlerts: string[];
  supplierOffers: SupplierOffer[];
  draftOrders: DraftOrder[];
  newReleaseAlerts: string[];
  pendingProposals: string[];
  createdOrders: { order_id?: number; supplier_name?: string; total_amount?: number }[];
  orderHistory: DecisionHistoryEntry[];
};

type AgentStateBridge = {
  setState: (state: ProcurementAgentState) => void;
  state?: unknown;
};

function buildDashboardViewState(state: ProcurementAgentState): DashboardViewState {
  const reorderProposals = state.data?.reorder_proposals ?? [];
  const supplierSelections = state.data?.supplier_selections ?? [];
  const draftOrders = state.data?.draft_orders ?? state.draft_orders ?? [];
  const purchaseOrderProposals =
    state.data?.purchase_order_proposals ?? state.purchase_order_proposals ?? [];
  const createdOrders = state.data?.created_orders ?? [];
  const decisionHistory = state.data?.decision_history ?? [];

  const inventoryAlerts = reorderProposals.map(
    (p) =>
      `${p.product_name ?? p.product_code ?? "Onbekend"}: ${p.current_qty ?? 0} op voorraad (min ${p.min_threshold ?? 0}), voorstel ${p.reorder_qty ?? 0}`,
  );

  const supplierOffers = supplierSelections.flatMap((selection) => selection.all_options ?? []);

  const newReleaseAlerts = (state.new_releases ?? []).map(
    (release) => `${release.title ?? "Onbekende release"} - ${release.artist ?? "Unknown artist"}`,
  );

  const pendingProposals = purchaseOrderProposals.map(
    (proposal) => `${proposal.product_name ?? "Onbekend product"} x ${proposal.quantity ?? 0}`,
  );

  return {
    inventoryAlerts,
    supplierOffers,
    draftOrders,
    newReleaseAlerts,
    pendingProposals,
    createdOrders,
    orderHistory: decisionHistory,
  };
}

/**
 * Component voor pad selectie: user kiest tussen leveranciers of nieuwe releases
 */
function PathSelectionPanel({ state, agent }: { state: ProcurementAgentState; agent: AgentStateBridge }) {
  const hasInventoryAlerts = (state.inventory_alerts?.length ?? 0) > 0;

  const handlePathChoice = (choice: "path_1_suppliers" | "path_2_new_releases") => {
    agent.setState({
      ...state,
      path_choice: choice,
      awaiting_path_selection: false,
    });
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
function ApprovalPanel({ state, agent }: { state: ProcurementAgentState; agent: AgentStateBridge }) {
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

    agent.setState({
      ...state,
      approval_order_indices: approvedIndices,
      rejection_reasons_by_index: localRejectionReasons,
      awaiting_human_approval: false,
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
  const { agent } = useAgent({
    agentId: AGENT_ID,
    updates: [UseAgentUpdate.OnStateChanged, UseAgentUpdate.OnRunStatusChanged],
  });

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
        title: "Maak conceptbestelling",
        message: "Maak een concept inkooporder voor urgente tekorten.",
      },
      {
        title: "Vraag goedkeuring",
        message: "Bereid human approval voor met duidelijke motivatie.",
      },
    ],
    available: "always",
  });

  const state = (agent.state as ProcurementAgentState) || INITIAL_AGENT_STATE;
  const viewState = useMemo(() => buildDashboardViewState(state), [state]);

  useEffect(() => {
    if (!agent.state) {
      agent.setState(INITIAL_AGENT_STATE);
    }
  }, [agent]);

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

        {/* ...existing code... */}
        {state.awaiting_path_selection && (
          <PathSelectionPanel
            state={{ ...state, inventory_alerts: viewState.inventoryAlerts }}
            agent={agent}
          />
        )}
        {state.awaiting_human_approval && <ApprovalPanel state={state} agent={agent} />}

        <section className="panel">
          <h2>Workflow Status</h2>
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
            {state.summary || state.message || "Nog geen samenvatting beschikbaar."}
          </div>
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
                    <td>-</td>
                    <td>{formatCurrency(offer.unit_price)}</td>
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
          <h2>Draft Orders</h2>
          <ul className="list">
            {viewState.draftOrders.length === 0 && <li>Geen conceptorders</li>}
            {viewState.draftOrders.map((order, idx) => (
              <li key={`draft-${idx}`}>
                {order.supplier_name || "Onbekende leverancier"} - {formatCurrency(order.total_amount)} ({(order.items || []).length} items)
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <h2>Order Geschiedenis</h2>
          <ul className="list">
            {viewState.orderHistory.length === 0 && <li>Nog geen orderhistorie beschikbaar</li>}
            {viewState.orderHistory.map((event, idx) => (
              <li key={`history-${idx}`}>
                {(event.timestamp || "-").replace("T", " ").slice(0, 16)} - {event.type || "event"}
                {event.supplier_name ? ` - ${event.supplier_name}` : ""}
                {event.po_id ? ` (#${event.po_id})` : ""}
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

