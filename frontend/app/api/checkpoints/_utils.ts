const backendUrl =
  process.env.PROCUREMENT_BACKEND_URL ||
  process.env.NEXT_PUBLIC_PROCUREMENT_BACKEND_URL ||
  "http://127.0.0.1:2024";

type LooseObject = Record<string, unknown>;

function normalizeBaseUrl(url: string) {
  return url.replace(/\/+$/, "");
}

function getBackendUrl() {
  return normalizeBaseUrl(backendUrl);
}

async function parseResponseBody(response: Response): Promise<LooseObject | unknown[] | string> {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return { error: text };
  }
}

async function langGraphRequest(path: string, init?: RequestInit): Promise<{ response: Response; data: LooseObject | unknown[] | string }> {
  const target = `${getBackendUrl()}${path}`;
  const response = await fetch(target, {
    cache: "no-store",
    ...init,
  });
  const data = await parseResponseBody(response);
  return { response, data };
}

function asObject(value: unknown): LooseObject {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as LooseObject;
  }
  return {};
}

function getErrorMessage(data: unknown, fallback: string) {
  const obj = asObject(data);
  const detail = typeof obj.detail === "string" ? obj.detail : undefined;
  const error = typeof obj.error === "string" ? obj.error : undefined;
  return detail || error || fallback;
}

function extractDraftOrders(state: LooseObject) {
  const nested = asObject(state.data).draft_orders;
  if (Array.isArray(nested)) {
    return nested;
  }

  const direct = state?.draft_orders;
  if (Array.isArray(direct)) {
    return direct;
  }

  return [];
}

function isPending(state: LooseObject) {
  if (!state || typeof state !== "object") {
    return false;
  }

  // Explicit human approval flag should always be treated as pending.
  if (Boolean(state.awaiting_human_approval)) {
    return true;
  }

  const step = String(state.step || "").toLowerCase();
  const status = String(state.status || "").toLowerCase();

  if (step !== "awaiting_human_input" && step !== "human_approval") {
    return false;
  }

  return (
    status === "proposed" ||
    status === "awaiting_approval" ||
    status === "awaiting_path_selection"
  );
}

function normalizeDecisionPayload(payload: unknown) {
  const source = asObject(payload);

  const approvedRaw = source.approved_indices;
  const approvedIndices = Array.isArray(approvedRaw)
    ? [...new Set<number>(
        approvedRaw
          .map((value: unknown) => Number(value))
          .filter((value: number) => Number.isFinite(value))
      )].sort((a: number, b: number) => a - b)
    : [];

  const rawReasons = asObject(source.rejection_reasons_by_index);
  const rejectionReasonsByIndex = Object.fromEntries(
    Object.entries(rawReasons)
      .map(([key, value]) => [Number(key), value])
      .filter(([key]) => Number.isFinite(key))
  );

  return {
    approvedIndices,
    rejectionReasonsByIndex,
    approvedBy: source.approved_by || "manager",
    decision: source.decision,
  };
}

export async function fetchPendingCheckpoints(limit: number) {
  const searchLimit = Math.max(limit * 3, 60);
  const { response, data } = await langGraphRequest("/threads/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      limit: searchLimit,
      sort_by: "updated_at",
      sort_order: "desc",
      select: ["thread_id", "status", "updated_at", "values"],
    }),
  });

  if (!response.ok) {
    const message = getErrorMessage(data, `Backend status ${response.status}`);
    return { status: response.status, data: { error: message } };
  }

  const threads = Array.isArray(data) ? data : [];
  const items = threads
    .map((thread) => {
      const threadObj = asObject(thread);
      const threadId = String(threadObj.thread_id ?? "").trim();
      if (!threadId) {
        return null;
      }

      const state = asObject(threadObj.values);
      if (!isPending(state)) {
        return null;
      }

      const draftOrders = extractDraftOrders(state);
      return {
        thread_id: threadId,
        step: state.step,
        status: state.status,
        message: state.message,
        approval_requested_at: state.approval_requested_at,
        updated_at: threadObj.updated_at,
        draft_orders_count: draftOrders.length,
        draft_orders: draftOrders,
      };
    })
    .filter(Boolean)
    .slice(0, Math.max(limit, 1));

  return { status: 200, data: { items, count: items.length } };
}

export async function fetchCheckpointState(threadId: string) {
  const { response, data } = await langGraphRequest(`/threads/${encodeURIComponent(threadId)}/state`, {
    method: "GET",
  });

  if (!response.ok) {
    const message = getErrorMessage(data, `Backend status ${response.status}`);
    return { status: response.status, data: { error: message } };
  }

  const payload = asObject(data);
  const state = asObject(payload.values && typeof payload.values === "object" ? payload.values : payload);
  const draftOrders = extractDraftOrders(state);
  return {
    status: 200,
    data: {
      thread_id: threadId,
      state,
      pending: isPending(state),
      draft_orders: draftOrders,
    },
  };
}

export async function submitCheckpointDecision(threadId: string, payload: unknown) {
  const normalized = normalizeDecisionPayload(payload);

  const { response, data } = await langGraphRequest(`/threads/${encodeURIComponent(threadId)}/runs/wait`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      assistant_id: "procurement_agent",
      command: {
        resume: {
          thread_id: threadId,
          approval_order_indices: normalized.approvedIndices,
          approved_indices: normalized.approvedIndices,
          rejection_reasons_by_index: normalized.rejectionReasonsByIndex,
          approved_by: normalized.approvedBy,
          approval_decision: normalized.decision || (normalized.approvedIndices.length > 0 ? "approved" : "rejected"),
          decision: normalized.decision || (normalized.approvedIndices.length > 0 ? "approved" : "rejected"),
        },
      },
    }),
  });

  if (!response.ok) {
    const message = getErrorMessage(data, `Backend status ${response.status}`);
    return { status: response.status, data: { error: message } };
  }

  const state = asObject(data);
  return {
    status: 200,
    data: {
      thread_id: threadId,
      state,
      pending: isPending(state),
    },
  };
}
