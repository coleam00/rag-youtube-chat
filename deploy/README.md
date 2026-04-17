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
```

## Secret hygiene

The real `.env` lives ONLY on the deploy host, in a directory owned by a non-factory user with mode 600. It is never committed, never shared via chat, and never readable by the Dark Factory workflow user.

---

## Cutover Runbook: SQLite → Postgres Migration

This section documents the one-time cutover from SQLite-backed chat storage to the Postgres-backed architecture. Perform this during a low-traffic maintenance window.

### Pre-cutover checklist

- [ ] New version deployed to staging and smoke-tested
- [ ] Postgres DB is healthy (`pg_isready` returns OK)
- [ ] Snapshot database (`dynachat_factory`) is available for testing
- [ ] DBA/oncall is aware (optional, for large datasets)
- [ ] Maintenance window announced if needed

### Step 1: Snapshot the SQLite database

Before cutting over, capture the current SQLite state:

```bash
# Copy directly from the live container's volume (blue is currently active)
docker cp dynachat-app-blue:/app/data/chat.db ./chat.db.$(date +%s).bak

# Or if the volume is mounted on the host:
cp /var/lib/docker/volumes/dynachat_app_data/_data/chat.db ./chat.db.$(date +%s).bak
```

Retain the `.bak` file for 30 days, then delete it.

### Step 2: Run the data migration script

On a machine with access to both the SQLite snapshot and the Postgres DB:

```bash
cd app/backend
uv run python -m backend.scripts.migrate_sqlite_to_pg ./chat.db.<timestamp>.bak
```

Enter the `DATABASE_URL` when prompted (or pass via `DATABASE_URL` env var).

Expected output:
```
Opening SQLite: ./chat.db.<timestamp>.bak
Connecting to Postgres…
Copying tables (FK order: videos → chunks → conversations → messages)…
  videos: N rows copied, Postgres count=N
  chunks: N rows copied, Postgres count=N
  conversations: N rows copied, Postgres count=N
  messages: N rows copied, Postgres count=N

Migration complete. Final counts:
  videos        : N
  chunks        : N
  conversations : N
  messages      : N
```

If any table reports a count mismatch, **stop and investigate** before proceeding. The migration script aborts on mismatch.

### Step 3: Deploy the Postgres version

The deploy is fully automated via the blue/green swap:

```bash
# The systemd timer picks up the new main automatically within 10 minutes
# Or trigger manually:
sudo systemctl start dynachat-deploy.service
```

Monitor the deploy:
```bash
docker logs dynachat-app-green --follow
```

### Step 4: Smoke-test the live deployment

```bash
# Health check
curl https://chat.dynamous.ai/api/health

# Expected: {"status":"ok","video_count":N,"chunk_count":N}

# Verify a conversation still exists
curl -H "Cookie: ..." https://chat.dynamous.ai/api/conversations

# Verify chat still works (send a message, verify citations)
```

### Step 5: Post-cutover verification queries

On the Postgres host:

```sql
-- Verify all tables are populated
SELECT 'videos'        AS tbl, COUNT(*) AS cnt FROM videos
UNION ALL SELECT 'chunks',        COUNT(*) FROM chunks
UNION ALL SELECT 'conversations', COUNT(*) FROM conversations
UNION ALL SELECT 'messages',       COUNT(*) FROM messages;

-- Verify no orphaned chunks (all video_ids reference existing videos)
SELECT COUNT(*) FROM chunks WHERE video_id NOT IN (SELECT id FROM videos);

-- Verify FK cascades work for conversations→messages
-- (should return 0 if ON DELETE CASCADE is correct)
SELECT COUNT(*) FROM messages m
WHERE NOT EXISTS (SELECT 1 FROM conversations c WHERE c.id = m.conversation_id);
```

### Rollback

If the Postgres deployment fails catastrophically:

1. Re-tag the old image or revert to the previous `main` commit
2. The `app_data` volume is still present (not deleted by this cutover — it can be orphaned but not removed automatically)
3. Restart the old container: `docker compose up -d --no-deps app-blue`

Rollback restores the SQLite-backed state. Re-run the migration script against the retained `.bak` after fixing the issue.

### Cleanup (30 days post-cutover)

```bash
# Delete the snapshot
rm ./chat.db.<timestamp>.bak

# Optionally remove the orphaned app_data volume
docker volume rm dynachat_app_data
```
