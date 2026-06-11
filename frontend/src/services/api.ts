import axios from "axios";

import type {
  ActivityPoint,
  AuthResponse,
  Conversation,
  DocumentItem,
  Message,
  OverviewStats,
  StreamEvent,
  User,
} from "../types";

const TOKEN_KEY = "documind_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(undefined, (error) => {
  // Expired/invalid session: clear the token and send the user to login.
  if (error.response?.status === 401 && window.location.pathname !== "/login") {
    setToken(null);
    window.location.href = "/login";
  }
  return Promise.reject(error);
});

// ---- Auth ----
export const register = (email: string, full_name: string, password: string) =>
  api.post<AuthResponse>("/auth/register", { email, full_name, password }).then((r) => r.data);

export const login = (email: string, password: string) =>
  api.post<AuthResponse>("/auth/login", { email, password }).then((r) => r.data);

export const fetchMe = () => api.get<User>("/auth/me").then((r) => r.data);

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
  const response = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken() ?? ""}`,
    },
    body: JSON.stringify({ content }),
  });

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
