export interface User {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface DocumentItem {
  id: number;
  filename: string;
  mime_type: string;
  file_size: number;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
  created_at: string;
  processed_at: string | null;
}

export interface Conversation {
  id: number;
  document_id: number | null;
  title: string;
  created_at: string;
}

export interface Source {
  ref: number;
  document_id: number;
  filename: string;
  chunk_index: number;
  snippet: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources: Source[] | null;
  created_at: string;
}

export interface OverviewStats {
  total_documents: number;
  ready_documents: number;
  total_conversations: number;
  questions_asked: number;
  chunks_indexed: number;
}

export interface ActivityPoint {
  date: string;
  documents_uploaded: number;
  questions_asked: number;
}

export type StreamEvent =
  | { type: "sources"; sources: Source[] }
  | { type: "token"; content: string }
  | { type: "done"; message_id: number }
  | { type: "error"; detail: string };
