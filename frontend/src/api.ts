export type CaseState = "open" | "evidence_received" | "recovered" | "closed";
export type Scenario = "fresh_cluster" | "stale" | "conflicting" | "low_accuracy";

export interface User { id: string; email: string }
export interface Device {
  id: string; nickname: string; model: string; imei_masked: string;
  status: string; verified_via: string | null; created_at: string;
}
export interface Challenge { channel: string; expires_at: string; code: string | null }
export interface CaseT { id: string; device_id: string; state: CaseState; opened_at: string; closed_at: string | null }
export interface Observation {
  id: string; source: string; observed_at: string; received_at: string;
  lat: number; lon: number; accuracy_m: number;
  validation_status: "accepted" | "flagged"; flags: string[]; age_seconds: number;
}
export interface SimulationItem { observed_at: string; status: string; flags: string[]; reason: string | null }
export interface Simulation { scenario: Scenario; results: SimulationItem[] }
export interface Finding { text: string; observation_ids: string[] }
export interface Explanation { headline: string; findings: Finding[]; guidance: string[]; uncertainty: string[] }
export interface Facts {
  total: number; accepted: number; flagged: number; flag_counts: Record<string, number>;
  latest_observed_at: string | null; all_simulated: boolean;
}
export interface ExplanationResponse {
  source: "ai" | "fallback"; model: string | null; fallback_reason: string | null;
  explanation: Explanation; facts: Facts; notice: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

const BASE = "/api";
const KEY = "tl_token";
let token: string | null = null;
try { token = sessionStorage.getItem(KEY); } catch { /* storage blocked: stay in memory */ }
let onUnauthorized: () => void = () => {};

export const auth = {
  get hasToken() { return token !== null; },
  set(t: string | null) {
    token = t;
    try { t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY); } catch { /* ignore */ }
  },
  onUnauthorized(fn: () => void) { onUnauthorized = fn; },
};

function messageFrom(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const d = detail[0] as { loc?: unknown[]; msg?: string };
    const field = d.loc?.[d.loc.length - 1];
    return field ? `${String(field)}: ${d.msg ?? "invalid"}` : (d.msg ?? "Invalid input");
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const o = detail as { message: string; reason?: string };
    return o.reason ? `${o.message} (${o.reason.replace(/_/g, " ")})` : o.message;
  }
  return status >= 500 ? "The server had a problem. Try again." : "Request failed";
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (res.status === 401 && token) { auth.set(null); onUnauthorized(); }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, messageFrom(data?.detail, res.status));
  return data as T;
}

export const api = {
  register: (email: string, password: string) => req<User>("POST", "/auth/register", { email, password }),
  login: (email: string, password: string) =>
    req<{ access_token: string }>("POST", "/auth/login", { email, password }),
  me: () => req<User>("GET", "/me"),
  devices: () => req<Device[]>("GET", "/devices"),
  device: (id: string) => req<Device>("GET", `/devices/${id}`),
  addDevice: (nickname: string, model: string, imei: string) =>
    req<Device>("POST", "/devices", { nickname, model, imei }),
  deleteDevice: (id: string) => req<void>("DELETE", `/devices/${id}`),
  challenge: (id: string) => req<Challenge>("POST", `/devices/${id}/ownership/challenge`),
  verify: (id: string, code: string) => req<Device>("POST", `/devices/${id}/ownership/verify`, { code }),
  cases: () => req<CaseT[]>("GET", "/cases"),
  case: (id: string) => req<CaseT>("GET", `/cases/${id}`),
  openCase: (deviceId: string) => req<CaseT>("POST", `/devices/${deviceId}/cases`),
  recovered: (id: string) => req<CaseT>("POST", `/cases/${id}/recovered`),
  close: (id: string) => req<CaseT>("POST", `/cases/${id}/close`),
  observations: (id: string) => req<Observation[]>("GET", `/cases/${id}/observations`),
  simulate: (id: string, scenario: Scenario) =>
    req<Simulation>("POST", `/cases/${id}/observations/simulate`, { scenario }),
  explain: (id: string) => req<ExplanationResponse>("POST", `/cases/${id}/explanation`),
};
