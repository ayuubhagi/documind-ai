import { Link } from "react-router-dom";

import { getToken } from "../services/api";

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
          <Link to="/register" className="btn-primary px-6 py-3 text-lg">
            Try it free
          </Link>
        </div>
      </section>

      <section className="mx-auto grid max-w-5xl gap-6 px-6 pb-24 sm:grid-cols-2">
        {features.map((f) => (
          <div key={f.title} className="card">
            <h3 className="mb-2 font-display text-lg font-semibold text-brand-400">{f.title}</h3>
            <p className="text-sm leading-relaxed text-slate-400">{f.body}</p>
          </div>
        ))}
      </section>

      <footer className="border-t border-slate-800 py-8 text-center text-sm text-slate-500">
        DocuMind AI — a RAG document intelligence platform. Built with React, FastAPI, PostgreSQL,
        ChromaDB &amp; Claude.
      </footer>
    </div>
  );
}
