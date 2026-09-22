import type {
  AlertsPayload,
  DispatchPlan,
  NodeDetail,
  SeasonReport,
  SettingsPayload,
  StackDetail,
  SubIndexWeights,
  VulnerabilityRubric,
  YardOverview,
} from "../types";

const BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  yard: () => request<YardOverview>("/api/yard"),
  stack: (id: string) => request<StackDetail>(`/api/stacks/${id}`),
  updateRubric: (id: string, rubric: VulnerabilityRubric) =>
    request(`/api/stacks/${id}/rubric`, { method: "POST", body: JSON.stringify(rubric) }),
  dispatch: () => request<DispatchPlan>("/api/dispatch"),
  override: (stack_id: string, override_reason_code: string, notes?: string) =>
    request("/api/dispatch/override", {
      method: "POST",
      body: JSON.stringify({ stack_id, override_reason_code, notes }),
    }),
  nodes: () => request<NodeDetail[]>("/api/nodes"),
  maintenance: (body: { node_id: string; stack_id: string; action_type: string; notes?: string; operator_role: string }) =>
    request("/api/nodes/maintenance", { method: "POST", body: JSON.stringify(body) }),
  season: () => request<SeasonReport>("/api/season"),
  alerts: () => request<AlertsPayload>("/api/alerts"),
  settings: () => request<SettingsPayload>("/api/settings"),
  solveAhp: (pairwise_matrix: number[][]) =>
    request<{
      normalized_weights: number[];
      sub_index_order: string[];
      lambda_max: number;
      consistency_ratio: number;
      is_consistent: boolean;
    }>("/api/settings/ahp/solve", { method: "POST", body: JSON.stringify({ pairwise_matrix }) }),
  applyWeights: (weights: SubIndexWeights, author: string, rationale: string) =>
    request("/api/settings/weights/apply", {
      method: "POST",
      body: JSON.stringify({ weights, author, rationale }),
    }),
  sensitivity: () => request<Record<string, unknown>>("/api/settings/sensitivity"),
  sim: (body: Record<string, unknown>) =>
    request("/api/sim/control", { method: "POST", body: JSON.stringify(body) }),
};
