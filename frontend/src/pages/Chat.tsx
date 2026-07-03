import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import UpgradeCard from "../components/UpgradeCard";
import { getConversation, listMessages, streamMessage, UpgradeRequiredError } from "../services/api";
import type { Conversation, Source } from "../types";

interface ChatMessage {
  id: number | null; // null while streaming
  role: "user" | "assistant";
  content: string;
  sources: Source[] | null;
  streaming?: boolean;
}

function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;
  return (
    <div className="mt-3 border-t border-slate-700/60 pt-2">
      <button
        className="text-xs font-medium text-brand-400 hover:underline"
        onClick={() => setOpen(!open)}
      >
        {open ? "Hide" : "Show"} {sources.length} source{sources.length > 1 ? "s" : ""}
      </button>
      {open && (
        <ul className="mt-2 space-y-2">
          {sources.map((s) => (
            <li key={s.ref} className="rounded-lg bg-slate-800/60 p-2 text-xs">
              <span className="font-semibold text-brand-400">[{s.ref}]</span>{" "}
              <span className="text-slate-300">{s.filename}</span>
              <p className="mt-1 line-clamp-3 text-slate-500">{s.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Chat() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const id = Number(conversationId);

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [upgradeReason, setUpgradeReason] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      const [convo, msgs] = await Promise.all([getConversation(id), listMessages(id)]);
      setConversation(convo);
      setMessages(
        msgs.map((m) => ({ id: m.id, role: m.role, content: m.content, sources: m.sources })),
      );
    })();
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;

    setInput("");
    setError(null);
    setBusy(true);

    // Optimistically render the user turn and an empty streaming assistant turn.
    setMessages((prev) => [
      ...prev,
      { id: null, role: "user", content: question, sources: null },
      { id: null, role: "assistant", content: "", sources: null, streaming: true },
    ]);

    try {
      await streamMessage(id, question, (event) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last.role !== "assistant") return prev;

          if (event.type === "sources") {
            next[next.length - 1] = { ...last, sources: event.sources };
          } else if (event.type === "token") {
            next[next.length - 1] = { ...last, content: last.content + event.content };
          } else if (event.type === "done") {
            next[next.length - 1] = { ...last, id: event.message_id, streaming: false };
          } else if (event.type === "error") {
            next[next.length - 1] = {
              ...last,
              streaming: false,
              content: last.content || "Something went wrong while generating the answer.",
            };
            setError(event.detail);
          }
          return next;
        });
      });
    } catch (err) {
      // Roll back the optimistic assistant bubble.
      setMessages((prev) => prev.slice(0, -1));
      if (err instanceof UpgradeRequiredError) {
        setUpgradeReason(err.message);
      } else {
        setError(
          err instanceof Error && err.message.includes("too fast")
            ? err.message
            : "Connection lost while streaming the answer. Please try again.",
        );
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold">{conversation?.title ?? "Chat"}</h1>
            <p className="text-xs text-slate-500">
              {conversation?.document_id
                ? "Scoped to one document"
                : "Searching across all your documents"}
            </p>
          </div>
          <Link to="/dashboard" className="btn-secondary text-sm">
            Back to documents
          </Link>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 && (
            <div className="py-20 text-center text-slate-500">
              <p className="text-lg">Ask anything about your documents.</p>
              <p className="mt-2 text-sm">
                e.g. “Summarize the key terms” or “What does section 4 say about payments?”
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-brand-500 text-slate-950"
                    : "border border-slate-800 bg-slate-900 text-slate-200"
                }`}
              >
                <p className="whitespace-pre-wrap">
                  {m.content}
                  {m.streaming && <span className="ml-1 animate-pulse text-brand-400">▍</span>}
                </p>
                {m.role === "assistant" && m.sources && <SourceList sources={m.sources} />}
              </div>
            </div>
          ))}
          {upgradeReason && <UpgradeCard reason={upgradeReason} />}
          <div ref={bottomRef} />
        </div>
      </div>

      <footer className="border-t border-slate-800 px-6 py-4">
        <form className="mx-auto flex max-w-3xl gap-3" onSubmit={(e) => void handleSend(e)}>
          <input
            className="input-field flex-1"
            placeholder="Ask a question about your documents…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy || Boolean(upgradeReason)}
            maxLength={8000}
          />
          <button type="submit" className="btn-primary" disabled={busy || !input.trim()}>
            {busy ? "Thinking…" : "Send"}
          </button>
        </form>
        {error && <p className="mx-auto mt-2 max-w-3xl text-xs text-red-400">{error}</p>}
      </footer>
    </div>
  );
}
