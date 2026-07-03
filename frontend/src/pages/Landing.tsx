import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchSampleInfo, getToken, streamSampleMessage } from "../services/api";
import type { Source } from "../types";

const features = [
  {
    title: "Upload anything",
    body: "PDFs, Word documents, Markdown, and plain text are extracted, chunked, and indexed automatically in the background.",
  },
  {
    title: "Ask in plain English",
    body: "Retrieval-augmented generation finds the most relevant passages and Claude writes a grounded answer in real time.",
  },
  {
    title: "Every answer cited",
    body: "Responses reference the exact excerpts they came from, so you can verify claims against the source document.",
  },
  {
    title: "See your usage",
    body: "A built-in analytics dashboard tracks documents indexed, questions asked, and activity over time.",
  },
];

function TrySample() {
  const [questions, setQuestions] = useState<string[]>([]);
  const [asked, setAsked] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSampleInfo()
      .then((info) => setQuestions(info.suggested_questions))
      .catch(() => setQuestions([]));
  }, []);

  if (questions.length === 0) return null;

  const ask = async (question: string) => {
    if (busy) return;
    setAsked(question);
    setAnswer("");
    setSources([]);
    setDone(false);
    setError(null);
    setBusy(true);
    try {
      await streamSampleMessage(question, (event) => {
        if (event.type === "token") setAnswer((prev) => prev + event.content);
        else if (event.type === "sources") setSources(event.sources);
        else if (event.type === "done") setDone(true);
        else if (event.type === "error") setError(event.detail);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong — try again.");
    } finally {
      setBusy(false);
      setDone(true);
    }
  };

  return (
    <section className="mx-auto max-w-3xl px-6 pb-20">
      <div className="card p-6 sm:p-8">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-500">
          Try it right now — no signup
        </p>
        <h2 className="mt-2 font-display text-2xl font-semibold">
          Ask our sample lease agreement anything
        </h2>
        <div className="mt-5 flex flex-wrap gap-2">
          {questions.map((q) => (
            <button
              key={q}
              className={`rounded-full border px-3.5 py-1.5 text-sm transition ${
                asked === q
                  ? "border-brand-500/60 bg-brand-500/10 text-brand-400"
                  : "border-slate-700 text-slate-300 hover:border-brand-500/40 hover:text-brand-400"
              }`}
              disabled={busy}
              onClick={() => void ask(q)}
            >
              {q}
            </button>
          ))}
        </div>

        {asked && (
          <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm leading-relaxed text-slate-200">
            <p className="whitespace-pre-wrap">
              {answer}
              {busy && <span className="ml-1 animate-pulse text-brand-400">▍</span>}
            </p>
            {sources.length > 0 && done && (
              <p className="mt-3 border-t border-slate-800 pt-2 text-xs text-slate-500">
                Grounded in {sources.length} passage{sources.length > 1 ? "s" : ""} from{" "}
                <span className="text-slate-400">{sources[0].filename}</span>
              </p>
            )}
            {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
          </div>
        )}

        {done && !error && (
          <div className="mt-5 flex items-center gap-4">
            <Link to="/register" className="btn-primary">
              Upload your own document — free
            </Link>
            <span className="text-xs text-slate-500">1 document · 10 questions/day free</span>
          </div>
        )}
      </div>
    </section>
  );
}

export default function Landing() {
  const isAuthed = Boolean(getToken());

  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div>
          <span className="font-display text-2xl font-bold text-brand-400">DocuMind</span>
          <span className="ml-1 text-xs uppercase tracking-widest text-slate-500">AI</span>
        </div>
        <nav className="flex items-center gap-3">
          <Link
            to="/pricing"
            className="px-2 text-sm text-slate-400 transition hover:text-slate-200"
          >
            Pricing
          </Link>
          {isAuthed ? (
            <Link to="/dashboard" className="btn-primary">
              Open app
            </Link>
          ) : (
            <>
              <Link to="/login" className="btn-secondary">
                Sign in
              </Link>
              <Link to="/register" className="btn-primary">
                Get started
              </Link>
            </>
          )}
        </nav>
      </header>

      <section className="mx-auto max-w-4xl px-6 pb-20 pt-16 text-center">
        <h1 className="font-display text-5xl font-bold leading-tight">
          Stop searching documents.
          <br />
          <span className="text-brand-400">Start asking them.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400">
          DocuMind turns your contracts, reports, papers, and notes into a knowledge base you can
          chat with — with every answer grounded in, and cited from, your own files.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <a href="#try" className="btn-primary px-6 py-3 text-lg">
            Try it free — no signup
          </a>
        </div>
      </section>

      <div id="try">
        <TrySample />
      </div>

      <section className="mx-auto grid max-w-5xl gap-6 px-6 pb-24 sm:grid-cols-2">
        {features.map((f) => (
          <div key={f.title} className="card">
            <h3 className="mb-2 font-display text-lg font-semibold text-brand-400">{f.title}</h3>
            <p className="text-sm leading-relaxed text-slate-400">{f.body}</p>
          </div>
        ))}
      </section>

      <footer className="border-t border-slate-800 py-8 text-center text-sm text-slate-500">
        DocuMind AI — a RAG document intelligence platform. Built with React, FastAPI, PostgreSQL
        &amp; ChromaDB.
      </footer>
    </div>
  );
}
