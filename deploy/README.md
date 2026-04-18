# Deploy

Production deployment via Docker Compose. Runs Caddy (TLS + reverse proxy) and Postgres (pgvector).

## First-time setup on a new VPS

1. Install Docker: https://docs.docker.com/engine/install/
2. Clone this repo to `/opt/dynachat/` (owned by a dedicated `dynachat` user, `chmod 700`)
3. Copy `.env.example` to `.env`, fill in real values (`chmod 600`)
4. Point DNS A record for your subdomain at the VPS public IP
5. `cd deploy && docker compose up -d`
6. Caddy auto-provisions a Let's Encrypt cert on first request

## Files

- `docker-compose.yml` - Caddy + Postgres services
- `Caddyfile` - reverse-proxy config (TLS + subdomain routing)
- `.env.example` - secret template (committed); real `.env` is gitignored

## Ports

- `80` / `443` (public) - Caddy
- `127.0.0.1:5433` (loopback only) - Postgres

## Environment variables

The app container reads these from `/opt/dynachat/.env` via docker-compose:

| Variable | Required | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | **yes** | OpenRouter embeddings + chat |
| `SUPADATA_API_KEY` | prod only | YouTube transcript fetch |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | **yes** | Postgres credentials used by both the `postgres` service and the app's `DATABASE_URL` |
| `JWT_SECRET` | **yes** (auth) | 32+ random bytes used to sign session-cookie JWTs. Generate with `openssl rand -hex 32`. Rotating this value invalidates all live sessions |
| `ADMIN_USER_EMAIL` | optional | Email of the single admin user (case-insensitive match). When unset, every `/api/admin/*` endpoint returns 403. Match MUST equal the email the admin registered with |

The app's `DATABASE_URL` is assembled from the `POSTGRES_*` values inside
`docker-compose.yml` — you do **not** set it directly in `.env`. It points at
the in-compose `postgres` service by DNS name.

Minimal `.env` for a fresh deploy:

```
OPENROUTER_API_KEY=sk-or-...
SUPADATA_API_KEY=...
POSTGRES_USER=dynachat
POSTGRES_PASSWORD=<random>
POSTGRES_DB=dynachat
JWT_SECRET=<openssl rand -hex 32>
ADMIN_USER_EMAIL=admin@yourdomain.com
```

## Secret hygiene

The real `.env` lives ONLY on the deploy host, in a directory owned by a non-factory user with mode 600. It is never committed, never shared via chat, and never readable by the Dark Factory workflow user.

## SQLite → Postgres cutover runbook

When migrating an existing production deployment from SQLite to Postgres:

### Prerequisites
- Postgres must be running and healthy (`postgres` service up)
- `DATABASE_URL` must be set correctly in `.env`
- `alembic.ini` must be present in the app container

### Step 1 — Snapshot SQLite (before cutover)
```bash
# On the host, inside the app container or at app/backend/data/
./scripts/dump_sqlite.sh
# Or manually:
cp /app/data/chat.db /app/data/chat.db.$(date +%s).bak
```

### Step 2 — Run Alembic migrations (first deploy with new build)
The app runs `alembic upgrade head` automatically on startup.
Verify it succeeded:
```bash
docker compose exec app-blue alembic --config /app/backend/alembic.ini current
# Should show: 0001 (or latest revision)
```

### Step 3 — Copy data from SQLite to Postgres (one-time)
```bash
# Run the migration script inside the app container
docker compose exec app-blue python -m backend.scripts.migrate_sqlite_to_pg /app/data/chat.db
# The script will prompt for DATABASE_URL (use the same one from .env)
```

### Step 4 — Verify
```bash
# Check row counts match between snapshot and Postgres
docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'SELECT count(*) from videos'
docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c 'SELECT count(*) from chunks'
```

### Step 5 — Restart app (ensures clean pool state)
```bash
docker compose restart app-blue app-green
```
