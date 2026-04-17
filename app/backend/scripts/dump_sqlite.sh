#!/bin/sh
# Snapshot the SQLite database before cutover.
# Usage: ./dump_sqlite.sh <destination_dir>
set -e

DEST="${1:-.}"
SRC="/opt/dark-factory/.archon/worktrees/dark-factory/app/archon/task-dark-factory-fix-github-issue-1776455142391/app/backend/data/chat.db"
TIMESTAMP="$(date +%s)"
DESTFILE="${DEST}/chat.db.${TIMESTAMP}.bak"

if [ ! -f "$SRC" ]; then
    echo "Error: SQLite database not found at $SRC" >&2
    exit 1
fi

cp "$SRC" "$DESTFILE"
echo "SQLite snapshot saved to: $DESTFILE"
echo "Retain for 30 days, then delete."
