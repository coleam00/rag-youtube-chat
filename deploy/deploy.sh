#!/usr/bin/env bash
# Blue/green deploy script for DynaChat. Polls git, rebuilds inactive color,
# waits for healthcheck, swaps Caddy upstream with graceful reload, stops old.
# Safe to run when blue/green isn't set up yet — it detects and no-ops.
#
# This file is the source-of-truth copy; the live VPS copy at
# /opt/dynachat/deploy.sh is kept in sync by hand. The systemd timer that
# drives it doesn't pull this from git, so changes here must be mirrored to
# the VPS to take effect.
set -euo pipefail

LOG=/var/log/dynachat-deploy.log
REPO=/opt/dynachat/app
COMPOSE_DIR=/opt/dynachat/app/deploy
UPSTREAM_FILE=/opt/dynachat/app/deploy/upstream.conf
LOCK=/var/run/dynachat-deploy.lock

exec >>"$LOG" 2>&1

# Concurrency guard — flock on LOCK fd
exec 200>"$LOCK"
flock -n 200 || { echo "[$(date -Iseconds)] another deploy running, exit"; exit 0; }

echo "[$(date -Iseconds)] ---- deploy check start ----"

cd "$REPO"
git fetch --quiet origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})
if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[$(date -Iseconds)] no changes (HEAD=$LOCAL)"
    exit 0
fi

echo "[$(date -Iseconds)] changes: $LOCAL -> $REMOTE, pulling"
git pull --ff-only --quiet

# Pull the latest paid Dynamous course/workshop transcripts (issue #147) into
# the host path that docker-compose mounts read-only into both colors. Loads
# /opt/dynachat/.env via `set -a` so the helper sees the deploy-key path and
# host-path overrides without leaking secrets to this script's stdout.
if [ -f /opt/dynachat/app/deploy/sync-dynamous-content.sh ]; then
    set -a
    # shellcheck disable=SC1091
    source /opt/dynachat/.env
    set +a
    bash /opt/dynachat/app/deploy/sync-dynamous-content.sh \
        || echo "[$(date -Iseconds)] sync-dynamous-content.sh failed (continuing with stale content)"
fi

cd "$COMPOSE_DIR"

# Reload Caddy reliably. `caddy reload` re-parses the Caddyfile (which imports
# upstream.conf), but in 2026-04 we hit a case where the live in-memory config
# kept dialing the old container even though upstream.conf on disk had been
# rewritten. Production 502'd until Caddy was hard-restarted. The fix: after
# `caddy reload`, check that the running Caddy config actually contains the
# expected upstream; if not, fall back to `docker restart` (~3s downtime,
# vastly better than an indefinite outage).
swap_caddy_upstream() {
    local expected="$1"   # e.g. "app-green:8000"
    sync
    docker compose --env-file /opt/dynachat/.env exec -T caddy \
        caddy reload --config /etc/caddy/Caddyfile || {
            echo "[$(date -Iseconds)] caddy reload returned non-zero — will verify and restart if needed"
        }

    # Verify reload took effect by reading the live admin-API config.
    sleep 1
    local live
    live=$(docker exec dynachat-caddy wget -qO- --timeout=3 \
        http://localhost:2019/config/ 2>/dev/null || echo "")
    if echo "$live" | grep -q "$expected"; then
        echo "[$(date -Iseconds)] caddy reload verified — routing to $expected"
        return 0
    fi

    echo "[$(date -Iseconds)] WARNING: caddy reload did not apply (live config missing '$expected'). Forcing restart."
    docker compose --env-file /opt/dynachat/.env restart caddy
    # Wait briefly for Caddy to come back. We're not strict here — if Caddy
    # itself is broken the next deploy attempt or a human will catch it.
    for i in $(seq 1 15); do
        if docker exec dynachat-caddy wget -qO- --timeout=2 \
            http://localhost:2019/config/ 2>/dev/null | grep -q "$expected"; then
            echo "[$(date -Iseconds)] caddy restart verified — routing to $expected"
            return 0
        fi
        sleep 1
    done
    echo "[$(date -Iseconds)] ERROR: caddy still not routing to $expected after restart"
    return 1
}

# Gate: require blue/green services + upstream.conf to exist before deploying
if ! docker compose --env-file /opt/dynachat/.env config --services 2>/dev/null | grep -q '^app-blue$'; then
    echo "[$(date -Iseconds)] blue/green not yet configured in compose — skipping. Rebuild caddy/postgres only if their configs changed (safe, no app dependency)."
    # Reload Caddy if its config changed. Postgres changes are manual (data volume).
    docker compose --env-file /opt/dynachat/.env up -d --no-deps caddy || true
    exit 0
fi

if [ ! -f "$UPSTREAM_FILE" ]; then
    echo "[$(date -Iseconds)] upstream.conf missing — initial deploy. Starting app-blue."
    echo 'reverse_proxy app-blue:8000' > "$UPSTREAM_FILE"
    docker compose --env-file /opt/dynachat/.env up -d --build app-blue
    # Wait for healthy
    for i in $(seq 1 900); do
        S=$(docker inspect --format='{{.State.Health.Status}}' dynachat-app-blue 2>/dev/null || echo missing)
        [ "$S" = "healthy" ] && break
        sleep 2
    done
    [ "$S" = "healthy" ] || { echo "[$(date -Iseconds)] app-blue failed healthcheck ($S)"; exit 1; }
    swap_caddy_upstream "app-blue:8000"
    echo "[$(date -Iseconds)] initial deploy complete: app-blue healthy"
    exit 0
fi

# Standard blue/green swap
ACTIVE=$(grep -oE 'app-(blue|green)' "$UPSTREAM_FILE" | head -1 | sed 's/app-//')
if [ "$ACTIVE" = "blue" ]; then INACTIVE=green; else INACTIVE=blue; fi
echo "[$(date -Iseconds)] active=$ACTIVE, deploying to $INACTIVE"

# Build + start inactive
docker compose --env-file /opt/dynachat/.env up -d --build --no-deps "app-$INACTIVE"

# Wait for inactive to be healthy (90s budget)
for i in $(seq 1 900); do
    S=$(docker inspect --format='{{.State.Health.Status}}' "dynachat-app-$INACTIVE" 2>/dev/null || echo missing)
    [ "$S" = "healthy" ] && break
    sleep 2
done
if [ "$S" != "healthy" ]; then
    echo "[$(date -Iseconds)] app-$INACTIVE unhealthy ($S) — aborting, keeping $ACTIVE live"
    docker compose --env-file /opt/dynachat/.env stop "app-$INACTIVE" || true
    exit 1
fi

# Flip Caddy upstream + graceful reload (zero dropped connections in the happy
# path; ~3s drop with restart fallback if reload misfires)
echo "reverse_proxy app-$INACTIVE:8000" > "$UPSTREAM_FILE"
swap_caddy_upstream "app-$INACTIVE:8000"

# Give in-flight requests a moment to drain from old upstream
sleep 5

# Stop old
docker compose --env-file /opt/dynachat/.env stop "app-$ACTIVE" || true
echo "[$(date -Iseconds)] deploy complete: $ACTIVE -> $INACTIVE"
