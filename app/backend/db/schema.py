"""
Database schema definitions and migration utilities.
Creates all four tables: videos, chunks, conversations, messages.
"""

import aiosqlite

from backend.config import DB_PATH

CREATE_VIDEOS_TABLE = """
CREATE TABLE IF NOT EXISTS videos (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    url         TEXT NOT NULL,
    transcript  TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CHUNKS_TABLE = """
CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    video_id    TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    embedding   TEXT NOT NULL,
    chunk_index INTEGER NOT NULL
);
"""

CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CONVERSATIONS_USER_ID_INDEX = """
CREATE INDEX IF NOT EXISTS conversations_user_id_idx ON conversations (user_id);
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CHANNEL_SYNC_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS channel_sync_runs (
    id           TEXT PRIMARY KEY,
    status       TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    videos_total INTEGER NOT NULL DEFAULT 0,
    videos_new   INTEGER NOT NULL DEFAULT 0,
    videos_error INTEGER NOT NULL DEFAULT 0,
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);
"""

CREATE_CHANNEL_SYNC_VIDEOS_TABLE = """
CREATE TABLE IF NOT EXISTS channel_sync_videos (
    id               TEXT PRIMARY KEY,
    sync_run_id      TEXT NOT NULL REFERENCES channel_sync_runs(id) ON DELETE CASCADE,
    youtube_video_id TEXT NOT NULL,
    status           TEXT NOT NULL CHECK(status IN ('pending', 'ingested', 'error')),
    error_message    TEXT,
    created_at       TEXT NOT NULL
);
"""

CREATE_CHANNEL_SYNC_VIDEOS_SYNC_RUN_ID_INDEX = """
CREATE INDEX IF NOT EXISTS channel_sync_videos_sync_run_id_idx ON channel_sync_videos (sync_run_id);
"""


async def _migrate_conversations_user_id(db: aiosqlite.Connection) -> None:
    """One-time migration: drop legacy conversations/messages tables if they
    predate the user_id column (see issue #56). The issue explicitly green-lit
    truncation — there was no real user data yet when auth shipped."""
    async with db.execute("PRAGMA table_info(conversations)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}
    if not columns:
        return  # Fresh DB; CREATE ... IF NOT EXISTS below will handle it
    if "user_id" in columns:
        return  # Already migrated
    await db.execute("DROP TABLE IF EXISTS messages")
    await db.execute("DROP TABLE IF EXISTS conversations")


async def init_db() -> None:
    """Create all tables if they do not already exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.execute(CREATE_VIDEOS_TABLE)
        await db.execute(CREATE_CHUNKS_TABLE)
        await _migrate_conversations_user_id(db)
        await db.execute(CREATE_CONVERSATIONS_TABLE)
        await db.execute(CREATE_CONVERSATIONS_USER_ID_INDEX)
        await db.execute(CREATE_MESSAGES_TABLE)
        await db.execute(CREATE_CHANNEL_SYNC_RUNS_TABLE)
        await db.execute(CREATE_CHANNEL_SYNC_VIDEOS_TABLE)
        await db.execute(CREATE_CHANNEL_SYNC_VIDEOS_SYNC_RUN_ID_INDEX)
        await db.commit()
    print(f"Database initialised at {DB_PATH}")
