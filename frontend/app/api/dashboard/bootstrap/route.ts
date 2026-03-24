import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

const backendUrl =
  process.env.PROCUREMENT_BACKEND_URL ||
  process.env.NEXT_PUBLIC_PROCUREMENT_BACKEND_URL ||
  "http://127.0.0.1:2024";

function normalizeBaseUrl(url: string) {
  return url.replace(/\/+$/, "");
}

type LooseObject = Record<string, unknown>;

type SalesEvent = {
  product_id?: number;
  quantity_sold?: number;
  sold_at?: string;
};

type Product = {
  product_id?: number;
  name?: string;
};

type Supplier = {
  supplier_id?: number;
  name?: string;
};

type PurchaseOrder = {
  purchase_order_id?: number;
  supplier_id?: number;
  status?: string;
  order_date?: string;
  expected_delivery_date?: string;
  delivery_date?: string;
  total_amount?: number;
  approved_by?: string;
};

type SupplierPerformance = {
  supplier_id?: number;
  total_orders?: number;
  late_deliveries?: number;
  reliability_score?: number;
  temporarily_unavailable?: boolean;
  last_rejection_reason?: string;
};

async function readJson<T>(fileName: string): Promise<T> {
  const dbPath = path.resolve(process.cwd(), "..", "db", fileName);
  const raw = await readFile(dbPath, "utf-8");
  return JSON.parse(raw) as T;
}

function toIso(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

function buildSalesVelocityForecasts(sales: SalesEvent[], products: Product[]) {
  const now = new Date();
  const cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  const productNameById = new Map<number, string>();

  for (const product of products) {
    if (typeof product.product_id === "number") {
      productNameById.set(product.product_id, product.name || String(product.product_id));
    }
  }

  const grouped = new Map<number, { total: number; first: number; last: number; events: number }>();

  for (const event of sales) {
    if (typeof event.product_id !== "number") continue;
    const qty = Number(event.quantity_sold || 0);
    if (!Number.isFinite(qty) || qty <= 0) continue;

    const soldAtIso = toIso(event.sold_at);
    if (!soldAtIso) continue;
    const soldAtMs = new Date(soldAtIso).getTime();
    if (soldAtMs < cutoff.getTime()) continue;

    const current = grouped.get(event.product_id);
    if (!current) {
      grouped.set(event.product_id, {
        total: qty,
        first: soldAtMs,
        last: soldAtMs,
        events: 1,
      });
      continue;
    }

    current.total += qty;
    current.events += 1;
    current.first = Math.min(current.first, soldAtMs);
    current.last = Math.max(current.last, soldAtMs);
  }

  return [...grouped.entries()]
    .map(([productId, stats]) => {
      const spanDays = Math.max(1, Math.floor((stats.last - stats.first) / (24 * 60 * 60 * 1000)) + 1);
      const velocityPerDay = stats.total / spanDays;
      return {
        product_id: productId,
        product_name: productNameById.get(productId) || String(productId),
        velocity_per_day: Number(velocityPerDay.toFixed(2)),
        predicted_stockout_date: null,
        reorder_basis: "30d_sales_window",
      };
    })
    .sort((a, b) => (b.velocity_per_day || 0) - (a.velocity_per_day || 0));
}

function normalizeSuppliers(raw: Supplier[] | LooseObject): Supplier[] {
  if (Array.isArray(raw)) return raw;
  if (raw && Array.isArray((raw as LooseObject).suppliers)) {
    return (raw as LooseObject).suppliers as Supplier[];
  }
  return [];
}

function buildApprovedOrders(orders: PurchaseOrder[], suppliers: Supplier[]) {
  const supplierNameById = new Map<number, string>();
  for (const supplier of suppliers) {
    if (typeof supplier.supplier_id === "number") {
      supplierNameById.set(supplier.supplier_id, supplier.name || String(supplier.supplier_id));
    }
  }

  return orders
    .filter((order) => {
      const status = String(order.status || "").toLowerCase();
      return status === "approved" || status === "delivered" || status === "orders_placed";
    })
    .sort((a, b) => {
      const aMs = new Date(a.order_date || 0).getTime();
      const bMs = new Date(b.order_date || 0).getTime();
      return bMs - aMs;
    })
    .slice(0, 50)
    .map((order) => ({
      order_id: order.purchase_order_id,
      supplier_id: order.supplier_id,
      supplier_name: typeof order.supplier_id === "number" ? supplierNameById.get(order.supplier_id) || "Unknown" : "Unknown",
      status: order.status,
      order_date: order.order_date,
      expected_delivery_date: order.expected_delivery_date,
      delivery_date: order.delivery_date,
      total_amount: order.total_amount,
      approved_by: order.approved_by,
    }));
}

function buildSupplierOffersFromPerformance(performanceRows: SupplierPerformance[], suppliers: Supplier[]) {
  const supplierNameById = new Map<number, string>();
  for (const supplier of suppliers) {
    if (typeof supplier.supplier_id === "number") {
      supplierNameById.set(supplier.supplier_id, supplier.name || String(supplier.supplier_id));
    }
  }

  return (performanceRows || [])
    .filter((row) => typeof row.supplier_id === "number")
    .map((row) => {
      const reliability = typeof row.reliability_score === "number" ? Number((row.reliability_score * 10).toFixed(2)) : undefined;
      let notes = `Late deliveries: ${row.late_deliveries ?? 0}, Total orders: ${row.total_orders ?? 0}`;
      if (row.temporarily_unavailable) {
        notes += " (Temporarily unavailable)";
      }
      if (row.last_rejection_reason) {
        notes += `. Last rejection: ${row.last_rejection_reason}`;
      }

      return {
        supplier_id: row.supplier_id,
        supplier_name: supplierNameById.get(row.supplier_id as number) || `Supplier ${row.supplier_id}`,
        unit_price: undefined,
        lead_time_days: undefined,
        reliability_score: reliability,
        notes,
      };
    })
    .sort((a, b) => (b.reliability_score || -1) - (a.reliability_score || -1));
}

async function localBootstrapPayload() {
  const [sales, products, orders, rawSuppliers, supplierPerformance] = await Promise.all([
    readJson<SalesEvent[]>("sales.json"),
    readJson<Product[]>("product.json"),
    readJson<PurchaseOrder[]>("purchase_order.json"),
    readJson<Supplier[] | LooseObject>("supplier.json"),
    readJson<SupplierPerformance[]>("supplier_performance.json"),
  ]);

  const suppliers = normalizeSuppliers(rawSuppliers);
  const salesVelocityForecasts = buildSalesVelocityForecasts(sales || [], products || []);
  const approvedOrders = buildApprovedOrders(orders || [], suppliers);
  const supplierOffers = buildSupplierOffersFromPerformance(supplierPerformance || [], suppliers);

  return {
    sales_velocity_forecasts: salesVelocityForecasts,
    approved_orders: approvedOrders,
    supplier_offers: supplierOffers,
    count: {
      sales_velocity_forecasts: salesVelocityForecasts.length,
      approved_orders: approvedOrders.length,
      supplier_offers: supplierOffers.length,
    },
    source: "local-db-fallback",
  };
}

export async function GET() {
  try {
    const target = `${normalizeBaseUrl(backendUrl)}/dashboard/bootstrap`;
    const response = await fetch(target, {
      method: "GET",
      cache: "no-store",
    });

    if (response.ok) {
      const text = await response.text();
      const payload = text ? JSON.parse(text) : {};
      return NextResponse.json(payload, { status: 200 });
    }

    const payload = await localBootstrapPayload();
    return NextResponse.json(payload, { status: 200 });
  } catch {
    try {
      const payload = await localBootstrapPayload();
      return NextResponse.json(payload, { status: 200 });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return NextResponse.json(
        { error: `Failed to fetch dashboard bootstrap: ${message}` },
        { status: 500 }
      );
    }
  }
}
