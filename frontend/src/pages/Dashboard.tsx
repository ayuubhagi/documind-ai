import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Link } from "react-router-dom";

import UpgradeCard from "../components/UpgradeCard";
import {
  createConversation,
  deleteConversation,
  deleteDocument,
  fetchUsage,
  listConversations,
  listDocuments,
  openBillingPortal,
  uploadDocument,
} from "../services/api";
import type { Conversation, DocumentItem, UsageSummary } from "../types";

const STATUS_BADGES: Record<DocumentItem["status"], string> = {
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  processing: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  failed: "bg-red-500/10 text-red-400 border-red-500/30",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [docs, convos] = await Promise.all([listDocuments(), listConversations()]);
    setDocuments(docs);
    setConversations(convos.slice(0, 8));
    fetchUsage().then(setUsage).catch(() => undefined);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll while any document is still being indexed so status badges update live.
  useEffect(() => {
    const hasInFlight = documents.some((d) => d.status === "pending" || d.status === "processing");
    if (!hasInFlight) return;
    const interval = setInterval(() => void refresh(), 4000);
    return () => clearInterval(interval);
  }, [documents, refresh]);

  const handleUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      await uploadDocument(file);
      await refresh();
    } catch (err: unknown) {
      const response = (err as { response?: { status?: number; data?: { detail?: unknown } } })
        .response;
      const detail = response?.data?.detail;
      if (response?.status === 402 && typeof detail === "object" && detail !== null) {
        setUpgradeReason((detail as { reason?: string }).reason ?? "Free limit reached.");
      } else {
        setError(typeof detail === "string" ? detail : "Upload failed. Please try again.");
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const startChat = async (documentId: number | null) => {
    const conversation = await createConversation(documentId);
    navigate(`/chat/${conversation.id}`);
  };

  const handleDeleteDocument = async (id: number) => {
    await deleteDocument(id);
    await refresh();
  };

  const handleDeleteConversation = async (id: number) => {
    await deleteConversation(id);
    await refresh();
  };

  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Documents</h1>
          <p className="mt-1 text-sm text-slate-400">
            Upload files, wait for indexing, then chat with them.
          </p>
        </div>
        <div className="flex gap-3">
          {readyCount > 0 && (
            <button className="btn-secondary" onClick={() => void startChat(null)}>
              Chat with all documents
            </button>
          )}
          <button
            className="btn-primary"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? "Uploading…" : "Upload document"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="hidden"
            onChange={(e) => void handleUpload(e)}
          />
        </div>
      </div>

      {usage && (
        <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-400">
          {usage.plan === "pro" ? (
            <>
              <span className="inline-block rounded-full border border-brand-500/40 bg-brand-500/10 px-2.5 py-0.5 text-xs font-medium text-brand-400">
                Pro
              </span>
              <button
                className="text-xs text-slate-500 hover:text-slate-300"
                onClick={() => void openBillingPortal().catch(() => undefined)}
              >
                Manage subscription
              </button>
            </>
          ) : (
            <>
              <span>
                {usage.questions_today}/{usage.question_limit} questions today ·{" "}
                {usage.documents_used}/{usage.document_limit} document
              </span>
              <Link to="/pricing" className="text-xs text-brand-400 hover:underline">
                Upgrade for unlimited
              </Link>
            </>
          )}
        </div>
      )}

      {upgradeReason && (
        <div className="mb-6">
          <UpgradeCard reason={upgradeReason} />
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {documents.length === 0 ? (
        <div className="card py-16 text-center">
          <p className="text-lg text-slate-300">No documents yet</p>
          <p className="mt-2 text-sm text-slate-500">
            Upload a PDF, Word document, Markdown, or text file to get started.
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-5 py-3">File</th>
                <th className="px-5 py-3">Size</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Chunks</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td className="max-w-xs truncate px-5 py-3 font-medium" title={doc.filename}>
                    {doc.filename}
                    {doc.status === "failed" && doc.error_message && (
                      <p className="mt-1 truncate text-xs text-red-400" title={doc.error_message}>
                        {doc.error_message}
                      </p>
                    )}
                  </td>
                  <td className="px-5 py-3 text-slate-400">{formatBytes(doc.file_size)}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGES[doc.status]}`}
                    >
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-slate-400">{doc.chunk_count || "—"}</td>
                  <td className="px-5 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      {doc.status === "ready" && (
                        <button
                          className="rounded-md px-2.5 py-1 text-xs font-medium text-brand-400 transition hover:bg-brand-500/10"
                          onClick={() => void startChat(doc.id)}
                        >
                          Chat
                        </button>
                      )}
                      <button
                        className="rounded-md px-2.5 py-1 text-xs font-medium text-slate-500 transition hover:bg-red-500/10 hover:text-red-400"
                        onClick={() => void handleDeleteDocument(doc.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {conversations.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-4 text-lg font-semibold">Recent conversations</h2>
          <div className="space-y-2">
            {conversations.map((c) => (
              <div
                key={c.id}
                className="card flex items-center justify-between px-4 py-3 transition hover:border-slate-700"
              >
                <button
                  className="flex-1 truncate text-left text-sm text-slate-200"
                  onClick={() => navigate(`/chat/${c.id}`)}
                >
                  {c.title}
                  <span className="ml-2 text-xs text-slate-500">
                    {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </button>
                <button
                  className="ml-3 rounded-md px-2 py-1 text-xs text-slate-500 transition hover:bg-red-500/10 hover:text-red-400"
                  onClick={() => void handleDeleteConversation(c.id)}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
