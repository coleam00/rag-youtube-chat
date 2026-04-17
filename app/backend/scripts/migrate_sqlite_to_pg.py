"""
One-shot migration script: copy data from a SQLite snapshot into Postgres.

Usage:
    uv run python -m backend.scripts.migrate_sqlite_to_pg <path_to_sqlite_db>

Run this BEFORE deploying the Postgres-only version. It:
1. Reads each table from SQLite (aiosqlite)
2. Writes to Postgres (asyncpg) in FK dependency order:
   videos → chunks → conversations → messages
3. Verifies row counts match after each table
4. Reports final counts

This script is a one-time use — do not run against a live production database.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import asyncpg


async def _parse_timestamp(raw: str) -> datetime:
    """Parse an ISO timestamp string, ensuring UTC timezone awareness."""
    # SQLite stores naive ISO strings; Postgres TIMESTAMPTZ needs tzinfo
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


async def _parse_embedding(raw: str) -> list[float]:
    """Parse a JSON embedding string into a Postgres REAL[] compatible list."""
    # json.loads returns Any — cast to list[float] since we control the input format
    return json.loads(raw)  # type: ignore[no-any-return]


async def _migrate_videos(sqlite_db: aiosqlite.Connection, pg_conn: asyncpg.Connection) -> int:
    """Copy videos table. Returns row count."""
    rows = await sqlite_db.execute_fetchall("SELECT * FROM videos")
    if not rows:
        return 0

    count = 0
    async with pg_conn.transaction():
        for row in rows:
            created_at = await _parse_timestamp(row["created_at"])
            await pg_conn.execute(
                """
                INSERT INTO videos (id, title, description, url, transcript, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                row["id"],
                row["title"],
                row["description"],
                row["url"],
                row["transcript"],
                created_at,
            )
            count += 1

    pg_count = await pg_conn.fetchval("SELECT COUNT(*) FROM videos")
    if count != pg_count:
        raise RuntimeError(f"videos: copied {count} but Postgres has {pg_count}")
    print(f"  videos: {count} rows copied, Postgres count={pg_count}")
    return count


async def _migrate_chunks(sqlite_db: aiosqlite.Connection, pg_conn: asyncpg.Connection) -> int:
    """Copy chunks table. Returns row count."""
    rows = await sqlite_db.execute_fetchall("SELECT * FROM chunks")
    if not rows:
        return 0

    count = 0
    async with pg_conn.transaction():
        for row in rows:
            embedding = await _parse_embedding(row["embedding"])
            await pg_conn.execute(
                """
                INSERT INTO chunks (id, video_id, content, embedding, chunk_index)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING
                """,
                row["id"],
                row["video_id"],
                row["content"],
                embedding,
                row["chunk_index"],
            )
            count += 1

    pg_count = await pg_conn.fetchval("SELECT COUNT(*) FROM chunks")
    if count != pg_count:
        raise RuntimeError(f"chunks: copied {count} but Postgres has {pg_count}")
    print(f"  chunks: {count} rows copied, Postgres count={pg_count}")
    return count


async def _migrate_conversations(
    sqlite_db: aiosqlite.Connection, pg_conn: asyncpg.Connection
) -> int:
    """Copy conversations table. Returns row count."""
    rows = await sqlite_db.execute_fetchall("SELECT * FROM conversations")
    if not rows:
        return 0

    count = 0
    async with pg_conn.transaction():
        for row in rows:
            created_at = await _parse_timestamp(row["created_at"])
            updated_at = await _parse_timestamp(row["updated_at"])
            await pg_conn.execute(
                """
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING
                """,
                row["id"],
                row["user_id"],
                row["title"],
                created_at,
                updated_at,
            )
            count += 1

    pg_count = await pg_conn.fetchval("SELECT COUNT(*) FROM conversations")
    if count != pg_count:
        raise RuntimeError(f"conversations: copied {count} but Postgres has {pg_count}")
    print(f"  conversations: {count} rows copied, Postgres count={pg_count}")
    return count


async def _migrate_messages(sqlite_db: aiosqlite.Connection, pg_conn: asyncpg.Connection) -> int:
    """Copy messages table. Returns row count."""
    rows = await sqlite_db.execute_fetchall("SELECT * FROM messages")
    if not rows:
        return 0

    count = 0
    async with pg_conn.transaction():
        for row in rows:
            created_at = await _parse_timestamp(row["created_at"])
            await pg_conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, created_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING
                """,
                row["id"],
                row["conversation_id"],
                row["role"],
                row["content"],
                created_at,
            )
            count += 1

    pg_count = await pg_conn.fetchval("SELECT COUNT(*) FROM messages")
    if count != pg_count:
        raise RuntimeError(f"messages: copied {count} but Postgres has {pg_count}")
    print(f"  messages: {count} rows copied, Postgres count={pg_count}")
    return count


async def run(sqlite_path: str, postgres_url: str) -> None:
    print(f"Opening SQLite: {sqlite_path}")
    print("Connecting to Postgres…")

    sqlite_db = await aiosqlite.connect(sqlite_path)
    sqlite_db.row_factory = aiosqlite.Row

    pool = await asyncpg.create_pool(dsn=postgres_url, min_size=1, max_size=5)

    try:
        async with pool.acquire() as pg_conn:
            print("Copying tables (FK order: videos → chunks → conversations → messages)…")
            videos = await _migrate_videos(sqlite_db, pg_conn)
            chunks = await _migrate_chunks(sqlite_db, pg_conn)
            conversations = await _migrate_conversations(sqlite_db, pg_conn)
            messages = await _migrate_messages(sqlite_db, pg_conn)

            print("\nMigration complete. Final counts:")
            print(f"  videos        : {videos}")
            print(f"  chunks        : {chunks}")
            print(f"  conversations : {conversations}")
            print(f"  messages      : {messages}")
    finally:
        await pool.close()
        await sqlite_db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python -m backend.scripts.migrate_sqlite_to_pg <path_to_sqlite_db>")
        sys.exit(1)

    sqlite_path = sys.argv[1]
    if not Path(sqlite_path).exists():
        print(f"Error: SQLite file not found: {sqlite_path}")
        sys.exit(1)

    postgres_url = input("Postgres DATABASE_URL: ").strip()
    if not postgres_url:
        print("Error: DATABASE_URL is required.")
        sys.exit(1)

    asyncio.run(run(sqlite_path, postgres_url))
