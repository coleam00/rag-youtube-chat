"""
Repository layer — all database access goes through this module.
No raw SQL lives in route handlers.

All tables use Postgres (asyncpg). The pool is acquired per-operation via
`get_pg_pool()` which is initialised in the FastAPI lifespan.
"""

import uuid
from datetime import UTC, datetime

from backend.db.postgres import get_pg_pool


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------


async def create_video(
    *,
    title: str,
    description: str,
    url: str,
    transcript: str,
) -> dict:
    vid_id = _new_id()
    now = _now()
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO videos (id, title, description, url, transcript, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            vid_id,
            title,
            description,
            url,
            transcript,
            now,
        )
    return {
        "id": vid_id,
        "title": title,
        "description": description,
        "url": url,
        "transcript": transcript,
        "created_at": now,
    }


async def get_video(video_id: str) -> dict | None:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM videos WHERE id = $1",
            video_id,
        )
    return dict(row) if row else None


async def list_videos() -> list[dict]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, description, url, created_at FROM videos ORDER BY created_at DESC"
        )
    return [dict(r) for r in rows]


async def count_videos() -> int:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) FROM videos")
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------


async def create_chunk(
    *,
    video_id: str,
    content: str,
    embedding: list[float],
    chunk_index: int,
) -> dict:
    chunk_id = _new_id()
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chunks (id, video_id, content, embedding, chunk_index)
            VALUES ($1, $2, $3, $4, $5)
            """,
            chunk_id,
            video_id,
            content,
            embedding,
            chunk_index,
        )
    return {
        "id": chunk_id,
        "video_id": video_id,
        "content": content,
        "embedding": embedding,
        "chunk_index": chunk_index,
    }


async def list_chunks() -> list[dict]:
    """Return all chunks with their embeddings (already REAL[] from Postgres)."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, video_id, content, embedding, chunk_index FROM chunks")
    return [dict(r) for r in rows]


async def list_chunks_for_video(video_id: str) -> list[dict]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, video_id, content, embedding, chunk_index FROM chunks
            WHERE video_id = $1 ORDER BY chunk_index
            """,
            video_id,
        )
    return [dict(r) for r in rows]


async def count_chunks() -> int:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) FROM chunks")
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


async def create_conversation(*, user_id: str, title: str = "New Conversation") -> dict:
    conv_id = _new_id()
    now = _now()
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (id, user_id, title, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            conv_id,
            user_id,
            title,
            now,
            now,
        )
    return {
        "id": conv_id,
        "user_id": user_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }


async def get_conversation(conv_id: str, user_id: str) -> dict | None:
    """Return the conversation only if it belongs to the given user."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
            conv_id,
            user_id,
        )
    return dict(row) if row else None


async def list_conversations(user_id: str) -> list[dict]:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.*,
                   (SELECT content
                    FROM messages
                    WHERE conversation_id = c.id
                    ORDER BY created_at DESC
                    LIMIT 1) AS preview
            FROM conversations c
            WHERE c.user_id = $1
            ORDER BY c.updated_at DESC
            """,
            user_id,
        )
    return [dict(r) for r in rows]


async def update_conversation_title(conv_id: str, user_id: str, title: str) -> bool:
    """Rename a conversation. Returns False if it does not belong to the user."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2",
            conv_id,
            user_id,
        )
        if not exists:
            return False
        await conn.execute(
            "UPDATE conversations SET title = $1, updated_at = $2 WHERE id = $3 AND user_id = $4",
            title,
            _now(),
            conv_id,
            user_id,
        )
        return True


async def touch_conversation(conv_id: str, user_id: str) -> None:
    """Update the updated_at timestamp (scoped to owner; silent no-op otherwise)."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE conversations SET updated_at = $1 WHERE id = $2 AND user_id = $3",
            _now(),
            conv_id,
            user_id,
        )


async def delete_conversation(conv_id: str, user_id: str) -> bool:
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        # ON DELETE CASCADE is defined at the Postgres level for messages
        deleted = await conn.fetchval(
            "DELETE FROM conversations WHERE id = $1 AND user_id = $2 RETURNING id",
            conv_id,
            user_id,
        )
        return deleted is not None


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


async def create_message(
    *,
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
) -> dict | None:
    """Insert a message. Returns None if the conversation does not belong to the user."""
    msg_id = _new_id()
    now = _now()
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        # Verify ownership atomically — INSERT only succeeds if the conversation
        # row exists for this user. Prevents cross-user message injection even
        # if a route handler forgets to check.
        inserted = await conn.fetchval(
            """
            INSERT INTO messages (id, conversation_id, role, content, created_at)
            SELECT $1, $2, $3, $4, $5
            WHERE EXISTS (
                SELECT 1 FROM conversations WHERE id = $6 AND user_id = $7
            )
            RETURNING id
            """,
            msg_id,
            conversation_id,
            role,
            content,
            now,
            conversation_id,
            user_id,
        )
        if inserted is None:
            return None
    await touch_conversation(conversation_id, user_id)
    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": now,
    }


async def list_messages(conversation_id: str, user_id: str) -> list[dict]:
    """Return messages only if the conversation belongs to the given user."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT m.*
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.conversation_id = $1 AND c.user_id = $2
            ORDER BY m.created_at ASC
            """,
            conversation_id,
            user_id,
        )
    return [dict(r) for r in rows]
