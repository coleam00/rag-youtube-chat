#!/usr/bin/env bash
# dump_sqlite.sh — snapshot chat.db to a timestamped backup file.
#
# Run from the app/backend/ directory (or any directory that contains data/chat.db):
#   ./scripts/dump_sqlite.sh
#
# Creates: data/chat.db.<timestamp>.bak
# Keeps the last 10 snapshots; purges older ones.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$BACKEND_DIR/data"
DB_FILE="$DATA_DIR/chat.db"
BACKUP_DIR="$DATA_DIR"

if [[ ! -f "$DB_FILE" ]]; then
    echo "No chat.db found at $DB_FILE — nothing to snapshot."
    exit 0
fi

TIMESTAMP="$(date +%s)"
BACKUP_PATH="$BACKUP_DIR/chat.db.$TIMESTAMP.bak"

cp "$DB_FILE" "$BACKUP_PATH"
echo "Snapshot created: $BACKUP_PATH"

# Purge backups older than 10 snapshots
cd "$BACKUP_DIR"
ls -1 chat.db.*.bak 2>/dev/null | sort -r | tail -n +11 | xargs -r rm -f
echo "Old backups pruned (keeping last 10)."