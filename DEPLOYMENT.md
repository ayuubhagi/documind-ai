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
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=<output of: python3 -c "import secrets; print(secrets.token_hex(32))">
POSTGRES_PASSWORD=<long random password>
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
- [ ] Anthropic API key has a spend limit set in the Console

## Alternative: managed platforms

If you'd rather not run a VPS, the two Dockerfiles deploy directly to **Railway**, **Render**, or **Fly.io**: create a Postgres add-on, set the same environment variables, deploy `backend/` and `frontend/` as two services, and route `/api` to the backend. Note ChromaDB and uploads need a persistent disk attached to the backend service.
