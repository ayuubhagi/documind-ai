import axios from "axios";

import type {
  ActivityPoint,
  AuthResponse,
  BillingConfig,
  Conversation,
  DocumentItem,
  Message,
  OverviewStats,
  SampleInfo,
  StreamEvent,
  UsageSummary,
  User,
} from "../types";

/** Thrown when the server responds 402 — the free-tier limit was hit. */
export class UpgradeRequiredError extends Error {
  constructor(reason: string) {
    super(reason);
    this.name = "UpgradeRequiredError";
  }
}

// Tokens live in localStorage. Tradeoff (documented in the README): storage is
// XSS-readable, but the API is same-origin behind React's escaping; httpOnly
// cookies would trade that for CSRF handling. Access tokens expire in 15
// minutes, so a leaked one has a short life; refresh tokens rotate on use and
// are revoked server-side on logout.
const TOKEN_KEY = "documind_token";
const REFRESH_KEY = "documind_refresh_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string | null, refresh: string | null): void {
  if (access) localStorage.setItem(TOKEN_KEY, access);
  else localStorage.removeItem(TOKEN_KEY);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  else localStorage.removeItem(REFRESH_KEY);
}

// Same-origin by default (dev proxy / docker nginx); VITE_API_URL points the
// static frontend at a separately hosted backend (e.g. Vercel -> Render).
const API_BASE = import.meta.env.VITE_API_URL ?? "";

const api = axios.create({ baseURL: `${API_BASE}/api` });

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Exchange the refresh token for a new token pair. Returns false if that fails. */
export async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    // Plain axios: the `api` instance's interceptor would recurse on 401.
    const res = await axios.post<AuthResponse>(`${API_BASE}/api/auth/refresh`, {
      refresh_token: refresh,
    });
    setTokens(res.data.access_token, res.data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

api.interceptors.response.use(undefined, async (error) => {
  const original = error.config;
  // On an expired access token, refresh once and retry the request.
  if (error.response?.status === 401 && original && !original._retried) {
    original._retried = true;
    if (await tryRefresh()) {
      original.headers.Authorization = `Bearer ${getToken()}`;
      return api.request(original);
    }
    // Refresh failed: session is over — clear and send the user to login.
    if (window.location.pathname !== "/login") {
      setTokens(null, null);
      window.location.href = "/login";
    }
  }
  return Promise.reject(error);
});

// ---- Auth ----
export const register = (email: string, full_name: string, password: string) =>
  api.post<AuthResponse>("/auth/register", { email, full_name, password }).then((r) => r.data);

export const login = (email: string, password: string) =>
  api.post<AuthResponse>("/auth/login", { email, password }).then((r) => r.data);

export const fetchMe = () => api.get<User>("/auth/me").then((r) => r.data);

export const logoutServerSide = () => {
  const refresh = getRefreshToken();
  // Best-effort revocation; local tokens are cleared regardless.
  if (refresh) api.post("/auth/logout", { refresh_token: refresh }).catch(() => undefined);
};

// ---- Documents ----
export const uploadDocument = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<DocumentItem>("/documents/upload", form).then((r) => r.data);
};

export const listDocuments = () => api.get<DocumentItem[]>("/documents").then((r) => r.data);

export const deleteDocument = (id: number) => api.delete(`/documents/${id}`);

// ---- Conversations ----
export const createConversation = (documentId: number | null) =>
  api
    .post<Conversation>("/conversations", { document_id: documentId })
    .then((r) => r.data);

export const listConversations = () =>
  api.get<Conversation[]>("/conversations").then((r) => r.data);

export const getConversation = (id: number) =>
  api.get<Conversation>(`/conversations/${id}`).then((r) => r.data);

export const listMessages = (conversationId: number) =>
  api.get<Message[]>(`/conversations/${conversationId}/messages`).then((r) => r.data);

export const deleteConversation = (id: number) => api.delete(`/conversations/${id}`);

// ---- Billing ----
export const fetchBillingConfig = () =>
  api.get<BillingConfig>("/billing/config").then((r) => r.data);

export const fetchUsage = () => api.get<UsageSummary>("/billing/usage").then((r) => r.data);

/** Starts Stripe Checkout and redirects the browser to the hosted payment page. */
export const startCheckout = async (): Promise<void> => {
  const { data } = await api.post<{ checkout_url: string }>("/billing/checkout");
  window.location.href = data.checkout_url;
};

/** Opens the Stripe customer portal (cancel / manage payment method). */
export const openBillingPortal = async (): Promise<void> => {
  const { data } = await api.post<{ portal_url: string }>("/billing/portal");
  window.location.href = data.portal_url;
};

// ---- Sample document (anonymous, pre-signup) ----
export const fetchSampleInfo = () => api.get<SampleInfo>("/sample").then((r) => r.data);

// ---- Analytics ----
export const fetchOverview = () =>
  api.get<OverviewStats>("/analytics/overview").then((r) => r.data);

export const fetchActivity = (days = 14) =>
  api.get<ActivityPoint[]>(`/analytics/activity?days=${days}`).then((r) => r.data);

// ---- Streaming chat (SSE over fetch) ----
// EventSource only supports GET without headers, so we parse the SSE frames
// from a POST fetch body manually.
export async function streamMessage(
  conversationId: number,
  content: string,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const send = () =>
    fetch(`${API_BASE}/api/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken() ?? ""}`,
      },
      body: JSON.stringify({ content }),
    });

  let response = await send();
  // Raw fetch bypasses the axios interceptor, so handle token expiry here too.
  if (response.status === 401 && (await tryRefresh())) {
    response = await send();
  }
  await readSseStream(response, onEvent);
}

/** Ask the public sample document a question (no auth). */
export async function streamSampleMessage(
  content: string,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/sample/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  await readSseStream(response, onEvent);
}

async function readSseStream(
  response: Response,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  if (response.status === 402) {
    const body = (await response.json()) as { detail?: { reason?: string } };
    throw new UpgradeRequiredError(body.detail?.reason ?? "Free limit reached.");
  }
  if (response.status === 429) {
    throw new Error("You're asking a little too fast — try again in a minute.");
  }
  if (!response.ok || !response.body) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (line.startsWith("data: ")) {
        onEvent(JSON.parse(line.slice(6)) as StreamEvent);
      }
    }
  }
}

export default api;
