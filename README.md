# DocuMind AI 📄✨

**Chat with your documents.** Upload PDFs, Word docs, or notes — DocuMind indexes them with a retrieval-augmented generation (RAG) pipeline and answers your questions in real time, with every claim cited back to the exact source passage.

> Full-stack AI engineering project: React · FastAPI · PostgreSQL · ChromaDB · Anthropic Claude · Docker · GitHub Actions

---

## Why this exists

Knowledge workers and students waste hours scanning long documents for specific answers. Ctrl+F finds words, not meaning. DocuMind solves this with semantic search + LLM generation: ask *"What are the termination conditions in this contract?"* and get a direct, cited answer in seconds.

## Features

- 🔐 **Accounts & auth** — JWT-based authentication with bcrypt password hashing
- 📤 **Document ingestion pipeline** — PDF/DOCX/TXT/MD → text extraction → paragraph-aware chunking → vector embedding, processed asynchronously in the background
- 🧠 **RAG chat** — semantic retrieval over your documents, grounded prompting, and token-by-token streaming answers from Claude
- 📎 **Citations** — every answer references the exact excerpts it was grounded in
- 🗂 **Per-document or global chat** — scope a conversation to one file or search everything
- 📊 **Analytics dashboard** — documents indexed, questions asked, and 14-day activity chart
- 🐳 **One-command deployment** — Docker Compose with Postgres, persistent volumes, and health checks
- ✅ **CI** — GitHub Actions runs linting, tests, typechecking, and Docker builds on every push

## Architecture

```
React (Vite + TS + Tailwind)
        │  REST + Server-Sent Events
        ▼
FastAPI ─────────────────────────────────────────────
 ├─ Auth (JWT + bcrypt)
 ├─ Documents API ──► BackgroundTask: extract → chunk → embed
 ├─ Conversations API ──► RAG: retrieve → ground → stream
 └─ Analytics API
        │                     │                  │
        ▼                     ▼                  ▼
   PostgreSQL            ChromaDB           Anthropic API
 (users, docs,        (chunk vectors,     (Claude Opus 4.8,
  convos, events)      semantic search)    streaming)
```

**RAG flow**: question → embed → top-k similarity search (scoped to your account) → excerpts injected into a grounded system prompt → Claude streams an answer citing `[1]`, `[2]`… → both turns persisted with sources.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Zustand, Recharts |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| LLM | Anthropic Claude (streaming + adaptive thinking) |
| Vector store | ChromaDB (local embeddings — no embedding API cost) |
| Database | PostgreSQL 16 |
| Auth | PyJWT + bcrypt |
| Infra | Docker, Docker Compose, nginx, GitHub Actions |

## Quickstart

### Docker (recommended)

```bash
cp .env.example .env        # add your ANTHROPIC_API_KEY
docker compose up --build
```

- App: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

### Manual (dev)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
export ANTHROPIC_API_KEY=sk-ant-...
export DATABASE_URL=sqlite:///./dev.db               # or point at Postgres
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev                                           # http://localhost:5173
```

### Tests & lint

```bash
cd backend
pytest                      # 8 tests, run against SQLite — no services needed
ruff check app tests        # lint (same check CI runs)

cd ../frontend
npm run build               # strict TypeScript typecheck + production build
```

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ for chat | — | Claude API access (get one at platform.claude.com) |
| `SECRET_KEY` | ✅ in prod | dev placeholder | JWT signing key — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | no | local Postgres | SQLAlchemy URL; use `sqlite:///./dev.db` for quick local dev |
| `POSTGRES_PASSWORD` | ✅ in prod | `postgres` | Database password (docker-compose) |
| `DOMAIN` | prod only | — | Your domain for automatic HTTPS (`docker-compose.prod.yml`) |
| `LLM_MODEL` | no | `claude-opus-4-8` | Claude model used for answers |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `RAG_TOP_K` | no | 1000 / 200 / 5 | RAG tuning knobs |

Copy `.env.example` → `.env` and fill in real values. `.env` files are git-ignored and must never be committed.

## API overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account, returns JWT |
| POST | `/api/auth/login` | Sign in, returns JWT |
| GET | `/api/auth/me` | Current user |
| POST | `/api/documents/upload` | Upload file; indexing runs in background |
| GET | `/api/documents` | List documents with processing status |
| DELETE | `/api/documents/{id}` | Delete document + its vectors |
| POST | `/api/conversations` | Start a conversation (one doc or all) |
| POST | `/api/conversations/{id}/messages` | Ask a question — streams SSE answer |
| GET | `/api/conversations/{id}/messages` | Conversation history with citations |
| GET | `/api/analytics/overview` | Workspace stats |
| GET | `/api/analytics/activity` | Daily uploads/questions for charting |

## Key engineering decisions

- **Streaming over SSE from a POST fetch** — `EventSource` can't send Authorization headers, so the client parses SSE frames from a streamed `fetch` body. nginx is configured with `proxy_buffering off` so tokens render as they're generated.
- **Background processing with isolated sessions** — document indexing runs in FastAPI BackgroundTasks with a dedicated DB session and never throws; failures land in the document row (`status=failed`, `error_message`) where the UI surfaces them.
- **Multi-tenant vector search** — one Chroma collection, every chunk tagged with `user_id`, every query filtered by it. Users can never retrieve each other's content.
- **Local embeddings** — ChromaDB's built-in model keeps the only paid API the LLM itself, and removes a network hop from ingestion.
- **Grounded prompting** — the system prompt instructs Claude to answer *only* from retrieved excerpts, cite them by number, and explicitly say when the documents don't contain the answer (anti-hallucination).

## Production deployment

A production compose file with automatic HTTPS is included — Caddy terminates TLS in front of the containers, and only ports 80/443 are exposed:

```bash
cp .env.example .env   # set DOMAIN, SECRET_KEY, ANTHROPIC_API_KEY, POSTGRES_PASSWORD
docker compose -f docker-compose.prod.yml up -d --build
```

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for the full VPS guide (DNS, backups, updates, security checklist) and managed-platform alternatives (Railway/Render/Fly.io).

## Screenshots

<!-- TODO: add screenshots/GIFs after first run:
  docs/screenshots/dashboard.png   — document list with processing status
  docs/screenshots/chat.png        — streaming answer with citations expanded
  docs/screenshots/analytics.png   — stats + activity chart
-->

| Dashboard | Chat with citations | Analytics |
|---|---|---|
| _coming soon_ | _coming soon_ | _coming soon_ |

## What this project demonstrates

Skills exercised end-to-end in this codebase (resume-ready bullets):

- Built a **full-stack RAG application** (React/TypeScript + FastAPI/PostgreSQL) that lets users chat with uploaded documents, with answers streamed token-by-token and grounded in cited source passages
- Designed an **asynchronous document-ingestion pipeline** (extract → chunk → embed → index) with status tracking, error recovery, and a multi-tenant ChromaDB vector store filtered per user
- Integrated the **Anthropic Claude API** with streaming Server-Sent Events, prompt engineering for citation-grounded answers, and graceful degradation on failures
- Implemented **JWT authentication**, ownership-checked REST APIs, and an append-only analytics event log powering a usage dashboard
- Shipped with **Docker Compose** (dev + production-with-HTTPS variants), **GitHub Actions CI** (lint, tests, typecheck, image builds), and a documented VPS deployment path

## Roadmap

- [ ] Alembic migrations (replace `create_all`)
- [ ] Celery + Redis for horizontally scalable ingestion
- [ ] Hybrid retrieval (BM25 + vectors) and reranking
- [ ] Document page-level citations with PDF preview
- [ ] Rate limiting & request quotas

## License

MIT
