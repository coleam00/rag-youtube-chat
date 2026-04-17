"""
Async Postgres connection pool via asyncpg.

All tables now live in Postgres (see CLAUDE.md "Active: Postgres"). The pool is
a module-level singleton created in the FastAPI lifespan handler; routes and
repos fetch it via `get_pg_pool()`.
"""

from __future__ import annotations

import logging

import asyncpg

from backend.config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


# Schema constants kept for reference — the initial Alembic migration
# (alembic/versions/0001_initial.py) uses these to construct raw SQL.
# Do not remove; they document the canonical schema.
USERS_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS users_email_idx ON users (email);

ALTER TABLE users DROP COLUMN IF EXISTS daily_message_count;
ALTER TABLE users DROP COLUMN IF EXISTS rate_window_start;

CREATE TABLE IF NOT EXISTS user_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_messages_user_id_created_at_idx
    ON user_messages (user_id, created_at DESC);
"""


SIGNUP_ATTEMPTS_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE IF NOT EXISTS signup_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ip INET NOT NULL,
    email_attempted CITEXT,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'accepted','ip_limited','global_limited','duplicate','invalid'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS signup_attempts_ip_created_at_idx
    ON signup_attempts (ip, created_at DESC);
CREATE INDEX IF NOT EXISTS signup_attempts_created_at_idx
    ON signup_attempts (created_at DESC);
"""


async def init_pg_pool() -> asyncpg.Pool:
    """Create the asyncpg pool if not already created. Idempotent."""
    global _pool
    if _pool is not None:
        return _pool
    logger.info("Connecting to Postgres…")
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
    )
    logger.info("Postgres pool ready.")
    return _pool


async def close_pg_pool() -> None:
    """Close the pool on shutdown. Idempotent."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def init_users_schema() -> None:
    """Stub for backwards compatibility with tests.

    Schema is now managed by Alembic migrations, not by this function.
    Kept for test compatibility only.
    """
    pass


def get_pg_pool() -> asyncpg.Pool:
    """Return the live pool. Raises if `init_pg_pool` was not called."""
    if _pool is None:
        raise RuntimeError(
            "Postgres pool is not initialised. Call init_pg_pool() in the "
            "FastAPI lifespan before using any Postgres-backed repository."
        )
    return _pool
