# DocuMind AI 📄✨

**Chat with your documents.** Upload PDFs, Word docs, or notes — DocuMind indexes them with a retrieval-augmented generation (RAG) pipeline and answers your questions in real time, with every claim cited back to the exact source passage.

> Full-stack AI engineering project: React · FastAPI · PostgreSQL · ChromaDB · pluggable LLM backends (demo / Groq / Anthropic Claude) · Docker · GitHub Actions

**[Live demo → documind-ai-hazel-theta.vercel.app](https://documind-ai-hazel-theta.vercel.app)** — free-tier hosting, so the first request after idle takes ~1 minute to wake the backend. Accounts and documents persist in managed Postgres; the vector index rebuilds automatically from stored chunks after restarts.

**Runs with zero API keys and zero cost out of the box** — the default `demo` provider streams canned responses through the real RAG pipeline, so you can clone, `docker compose up`, and try everything without creating an account anywhere.

---

## Why this exists

Knowledge workers and students waste hours scanning long documents for specific answers. Ctrl+F finds words, not meaning. DocuMind solves this with semantic search + LLM generation: ask *"What are the termination conditions in this contract?"* and get a direct, cited answer in seconds.

## Features

- 🔐 **Accounts & auth** — short-lived JWT access tokens + rotating, server-side-revocable refresh tokens; bcrypt password hashing
- 📤 **Document ingestion pipeline** — PDF/DOCX/TXT/MD → text extraction → paragraph-aware chunking → vector embedding, processed asynchronously in the background
- 🧠 **RAG chat** — semantic retrieval over your documents, grounded prompting, and token-by-token streaming answers
- 🔌 **Pluggable LLM backends** — `demo` (free, no API), Groq (free tier), or Anthropic Claude via one config flag
- 📎 **Citations** — every answer references the exact excerpts it was grounded in
- 🗂 **Per-document or global chat** — scope a conversation to one file or search everything
- 📊 **Analytics dashboard** — documents indexed, questions asked, and 14-day activity chart
- 🐳 **One-command deployment** — Docker Compose with Postgres, persistent volumes, and health checks
- ✅ **CI** — GitHub Actions runs linting, tests, typechecking, and Docker builds on every push
- 🛡 **Hardened API** — per-user rate limiting, magic-byte upload validation, prompt-injection mitigations, Alembic migrations (see [Security considerations](#security-considerations))

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
   PostgreSQL            ChromaDB           LLM provider
 (users, docs,        (chunk vectors,    (demo | Groq |
  convos, events)      semantic search)   Claude, streaming)
```

**RAG flow**: question → embed → top-k similarity search (scoped to your account) → excerpts injected into a grounded system prompt → the LLM streams an answer citing `[1]`, `[2]`… → both turns persisted with sources.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Zustand, Recharts |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| LLM | Pluggable: demo (offline) / Groq / Anthropic Claude — all streaming |
| Vector store | ChromaDB (local embeddings — no embedding API cost) |
| Database | PostgreSQL 16 |
| Auth | PyJWT (access + rotating refresh tokens) + bcrypt |
| Rate limiting | slowapi (per-user keys) |
| Migrations | Alembic |
| Infra | Docker, Docker Compose, nginx, GitHub Actions |

## Quickstart

### Docker (recommended)

```bash
docker compose up --build   # no .env needed — runs in free demo mode
```

- App: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

Want real model answers? Copy `.env.example` → `.env` and set either:

- `LLM_PROVIDER=groq` + `GROQ_API_KEY` — free tier at [console.groq.com](https://console.groq.com), no payment method required
- `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` — paid per token ([platform.claude.com](https://platform.claude.com))

### Manual (dev)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/documind
alembic upgrade head                                  # create/upgrade the schema
uvicorn app.main:app --reload                         # demo mode by default

# Frontend (new terminal)
cd frontend
npm install
npm run dev                                           # http://localhost:5173
```

### Tests & lint

```bash
cd backend
pytest                      # runs against SQLite — no services or API keys needed
ruff check app tests        # lint (same check CI runs)

cd ../frontend
npm run build               # strict TypeScript typecheck + production build
```

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LLM_PROVIDER` | no | `demo` | `demo` (offline, free), `groq`, or `anthropic` |
| `GROQ_API_KEY` | if `groq` | — | Free at console.groq.com — no payment method needed |
| `ANTHROPIC_API_KEY` | if `anthropic` | — | Paid per token (platform.claude.com) |
| `SECRET_KEY` | ✅ in prod | dev placeholder | JWT signing key — generate with `python -c "import secrets; print(secrets.token_hex(32))"`. The app **refuses to start** in production with the dev default. |
| `ENVIRONMENT` | no | `development` | Set `production` to enforce the SECRET_KEY check |
| `DATABASE_URL` | no | local Postgres | SQLAlchemy URL |
| `POSTGRES_PASSWORD` | ✅ in prod | `postgres` | Database password (docker-compose) |
| `DOMAIN` | prod only | — | Your domain for automatic HTTPS (`docker-compose.prod.yml`) |
| `LLM_MODEL` / `GROQ_MODEL` | no | Opus 4.8 / Llama 3.3 70B | Model per provider |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `RAG_TOP_K` | no | 1000 / 200 / 5 | RAG tuning knobs |

Copy `.env.example` → `.env` and fill in real values. `.env` files are git-ignored and must never be committed.

## API overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Create account, returns access + refresh tokens |
| POST | `/api/auth/login` | Sign in, returns access + refresh tokens |
| POST | `/api/auth/refresh` | Rotate a refresh token for a new pair |
| POST | `/api/auth/logout` | Revoke a refresh token server-side |
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
- **Grounded prompting** — the system prompt instructs the model to answer *only* from retrieved excerpts, cite them by number, and explicitly say when the documents don't contain the answer (anti-hallucination).
- **Demo provider as a first-class backend** — the `demo` LLM runs the entire pipeline (embed → retrieve → rank → cite → stream) and only substitutes the final generation step, so the app is fully demonstrable at zero cost and CI never needs a secret.

## Security considerations

Security posture and the reasoning behind it — including known, accepted tradeoffs:

**Authentication.** Access tokens are JWTs that live 15 minutes; sessions persist via refresh tokens that rotate on every use and are recorded server-side, so logout actually revokes them and a replayed (stolen-then-rotated) refresh token nukes every session for that user. The signing algorithm is pinned on decode (no algorithm-confusion), and a `type` claim stops refresh tokens being replayed as access tokens. Passwords are bcrypt-hashed and capped at 72 bytes because bcrypt silently ignores anything longer.

**Tokens in localStorage — accepted tradeoff.** Tokens are readable by successful XSS, whereas `httpOnly` cookies wouldn't be. The mitigations: React escapes rendered content by default, no `dangerouslySetInnerHTML` is used, access tokens expire in 15 minutes, and refresh tokens are revocable. Cookies would trade the XSS exposure for CSRF handling plus cross-origin complexity; for this architecture the short-token + revocation design was the deliberate choice.

**Rate limiting.** slowapi enforces per-user limits (falling back to per-IP when anonymous): login 10/min, register 10/hr, upload 30/hr, and chat 20/min + 200/day. Chat is the tightest because each call can trigger a paid LLM request — the daily cap bounds the worst-case API spend from any single account. Limits are in-memory (correct for the single-process deployment); a Redis backend is the documented path if the API ever scales out.

**Prompt injection — known and mitigated, not eliminated.** Uploaded documents are untrusted input that ends up inside the LLM prompt, so a document containing "ignore previous instructions…" can try to steer the model. Blast radius is inherently small: the model has no tools, and retrieval is scoped to the uploader's own account, so an attacker can only poison their own answers. Excerpts are additionally wrapped in `<document_excerpts>` delimiters with an explicit system rule that delimited content is data, not instructions. This raises the bar; no prompt-level defense is airtight, which is why the model has no capabilities worth hijacking.

**Uploads.** Files are validated by extension *and* magic bytes (a renamed `.exe` is rejected before processing), size-capped, stored under server-generated UUID names so user-supplied filenames never touch the filesystem, and namespaced per user.

**Tenant isolation.** Every document/conversation route checks ownership (returning 404, not 403, so IDs can't be enumerated), every vector-store query *and delete* filters on `user_id`, and all SQL goes through the SQLAlchemy ORM with bound parameters.

**Error hygiene.** Raw exception strings from parsing libraries can leak internals (server paths, library versions); processing failures store a generic message in the API-visible field and keep the real traceback in server logs.

**Secrets.** No secrets are committed. The dev `SECRET_KEY` fallback is public by design, and the app refuses to start in production (`ENVIRONMENT=production`) while it's in use; the prod compose file also hard-fails if `SECRET_KEY` is unset.

## Production deployment

A production compose file with automatic HTTPS is included — Caddy terminates TLS in front of the containers, and only ports 80/443 are exposed:

```bash
cp .env.example .env   # set DOMAIN, SECRET_KEY, POSTGRES_PASSWORD (+ LLM provider if desired)
docker compose -f docker-compose.prod.yml up -d --build
```

Database schema is managed by Alembic — the backend container runs `alembic upgrade head` on start, so migrations apply automatically on deploy.

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
- Built a **pluggable LLM provider layer** (offline demo / Groq / Anthropic Claude) with streaming Server-Sent Events, prompt engineering for citation-grounded answers, and graceful degradation on failures
- Implemented **JWT auth with rotating refresh tokens and server-side revocation**, per-user rate limiting, ownership-checked REST APIs, and an append-only analytics event log powering a usage dashboard
- Wrote up a **threat model and security tradeoffs** (prompt injection, token storage, abuse limits) and enforced them in code — startup guards, magic-byte validation, tenant-scoped vector search
- Shipped with **Docker Compose** (dev + production-with-HTTPS variants), **GitHub Actions CI** (lint, tests, typecheck, image builds), and a documented VPS deployment path

## Roadmap

- [x] Alembic migrations (replaced `create_all`)
- [x] Rate limiting & request quotas
- [x] Refresh tokens with rotation and server-side revocation
- [ ] Celery + Redis for horizontally scalable ingestion
- [ ] Hybrid retrieval (BM25 + vectors) and reranking
- [ ] Document page-level citations with PDF preview

## License

MIT
