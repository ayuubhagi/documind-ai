# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**DocuMind AI** — a RAG-powered document intelligence platform. Users upload documents (PDF/DOCX/TXT/MD), the backend extracts → chunks → embeds them into ChromaDB, and users chat with their documents via streaming, citation-grounded answers from Claude.

## Stack

- **Backend**: FastAPI + SQLAlchemy 2.0 + PostgreSQL, ChromaDB (vectors), Anthropic SDK (Claude Opus 4.8)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind + Zustand + Recharts
- **Infra**: Docker Compose, GitHub Actions CI

## Commands

```bash
# Backend (from backend/)
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements-dev.txt
uvicorn app.main:app --reload                      # http://localhost:8000, docs at /docs
pytest                                             # tests use SQLite, no Postgres needed
ruff check app tests

# Frontend (from frontend/)
npm install
npm run dev                                        # http://localhost:5173, proxies /api -> :8000
npm run build                                      # typecheck + production build

# Full stack
docker compose up --build                          # frontend :3000, backend :8000, postgres
```

Backend needs `ANTHROPIC_API_KEY` (env or `backend/.env`). Without Postgres running, set `DATABASE_URL=sqlite:///./dev.db` for quick local dev.

## Architecture notes

- **Request flow**: React → (`/api` proxy) → FastAPI routes (`app/api/routes/`) → services (`app/services/`) → Postgres / ChromaDB / Anthropic.
- **Ingestion** (`services/ai/document_processor.py`): runs as a FastAPI `BackgroundTask` with its **own DB session** (request session is closed by then). Status transitions: `pending → processing → ready|failed`. Frontend polls `/api/documents` while any doc is in-flight.
- **RAG** (`services/ai/rag.py`): retrieve top-k chunks from Chroma (always filtered by `user_id` — this is the multi-tenancy boundary) → grounded system prompt with numbered excerpts → stream Claude tokens as SSE frames → persist both turns. SSE event types: `sources`, `token`, `done`, `error`.
- **Streaming**: backend returns `StreamingResponse(text/event-stream)`; frontend parses SSE from a POST `fetch` body (EventSource can't send auth headers). nginx config disables `proxy_buffering` for `/api/` — do not remove that.
- **Auth**: JWT bearer tokens (PyJWT) + bcrypt. `app/api/deps.py:get_current_user` guards every non-auth route. Token stored in localStorage under `documind_token`.
- **Analytics**: append-only `analytics_events` table written via `services/analytics.track_event` (caller commits). Dashboard aggregates it in `routes/analytics.py`.
- **Schema**: created via `Base.metadata.create_all` on startup (no Alembic yet). New models must be imported in `app/models/__init__.py` to be registered.

## Conventions

- Python: ruff, line length 100, SQLAlchemy 2.0 typed `Mapped[]` style, routes stay thin — logic lives in `services/`.
- Ownership checks: every resource route must verify `resource.user_id == current_user.id` (see `_get_owned_*` helpers).
- TypeScript: strict mode; API calls only through `src/services/api.ts`; shared types in `src/types/index.ts`.
- Claude model is configured via `LLM_MODEL` setting — don't hardcode model strings elsewhere.
