# Deploying DocuMind AI

Production architecture: a single VPS running Docker Compose, with **Caddy** terminating HTTPS (automatic Let's Encrypt certificates) in front of the frontend and backend containers. Postgres, uploaded files, and the vector index live in named Docker volumes.

```
Internet ──► Caddy (:443, auto-TLS)
              ├── /api/* ──► backend (FastAPI)
              └── /*     ──► frontend (nginx + React build)
                              backend ──► db (Postgres)
                              backend ──► volumes (uploads, chroma)
```

## 1. Provision a server

Any Ubuntu 22.04+ VPS with ≥2 GB RAM works (Hetzner CX22, DigitalOcean Basic, AWS Lightsail/EC2). Then install Docker:

```bash
curl -fsSL https://get.docker.com | sh
```

## 2. Point your domain at it

Create a DNS **A record** for your domain (e.g. `documind.yourdomain.com`) pointing to the server's IP. Caddy needs this resolvable before it can issue a certificate.

## 3. Configure and launch

```bash
git clone https://github.com/<you>/documind.git && cd documind
cp .env.example .env
nano .env
```

Set in `.env`:

```env
DOMAIN=documind.yourdomain.com
SECRET_KEY=<output of: python3 -c "import secrets; print(secrets.token_hex(32))">
POSTGRES_PASSWORD=<long random password>

# Optional — omit entirely to run in free demo mode (no AI spend possible)
LLM_PROVIDER=groq          # or: anthropic
GROQ_API_KEY=gsk_...
```

Then:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

First start takes a few minutes (image builds + the embedding model downloads on first document upload). Visit `https://<your-domain>` — Caddy serves a valid certificate automatically.

## 4. Operations

```bash
# Logs
docker compose -f docker-compose.prod.yml logs -f backend

# Deploy an update
git pull
docker compose -f docker-compose.prod.yml up -d --build

# Database backup
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U postgres documind > backup_$(date +%F).sql

# Restore
cat backup_2026-06-11.sql | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U postgres documind
```

Uploaded files and the vector index live in the `uploads` and `chroma` volumes; back them up with `docker run --rm -v documind_uploads:/data -v $(pwd):/backup alpine tar czf /backup/uploads.tgz /data` (same pattern for `chroma`).

## Security checklist

- [ ] `SECRET_KEY` and `POSTGRES_PASSWORD` are long and random (never the dev defaults)
- [ ] `.env` is not committed (it's in `.gitignore`)
- [ ] Only ports 80/443 are exposed — backend and Postgres are internal-only in `docker-compose.prod.yml`
- [ ] Server firewall (e.g. `ufw allow 80,443/tcp && ufw enable`) and SSH key auth
- [ ] If using a paid provider: spend limit set in its console, or use `LLM_PROVIDER=groq` (free tier) / `demo` (no API at all)
- [ ] Rate limits are active by default (login, register, upload, chat) — they cap worst-case API spend per account

## Free hosting (Render backend + Vercel frontend)

A zero-cost live demo, no credit card anywhere:

1. **Backend on Render (free tier):** sign in at [render.com](https://render.com) with GitHub → **New → Blueprint** → select this repo. `render.yaml` provisions everything: demo LLM provider (no AI spend possible) and a generated `SECRET_KEY`. Set `DATABASE_URL` in the dashboard to a managed Postgres instance (free Neon tier works) so accounts, plans, and document chunks survive restarts; the Chroma vector index lives on ephemeral disk and is rebuilt lazily from stored chunks (`app/services/ai/reindex.py`). Note the service URL, e.g. `https://documind-backend.onrender.com`.
2. **Frontend on Vercel:** import the repo, set **Root Directory** to `frontend`, and add env var `VITE_API_URL=https://<your-render-url>`. Redeploy.
3. If your Vercel domain differs from the one in `render.yaml`, update `CORS_ORIGINS` in the Render dashboard.

Free-tier caveats: the backend sleeps after 15 idle minutes (first request takes ~1 min to wake), and the first question after a restart pays a one-time reindexing delay while vectors rebuild. Original uploaded files are not retained after text extraction. For always-on hosting, use the VPS path above.

## Alternative: managed platforms

If you'd rather not run a VPS, the two Dockerfiles deploy directly to **Railway**, **Render**, or **Fly.io**: create a Postgres add-on, set the same environment variables, deploy `backend/` and `frontend/` as two services, and route `/api` to the backend. Note ChromaDB and uploads need a persistent disk attached to the backend service.
