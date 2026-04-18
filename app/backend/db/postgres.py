"""
Async Postgres connection pool.

The pool is a module-level singleton created in the FastAPI lifespan handler;
routes and repos fetch it via `get_pg_pool()`. All schema management is handled
by Alembic migrations.
"""

from __future__ import annotations

import logging

import asyncpg

from backend.config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pg_pool() -> asyncpg.Pool:
    """Create the asyncpg pool if not already created. Idempotent."""
    global _pool
    if _pool is not None:
        return _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set; cannot initialise Postgres pool.")
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


def get_pg_pool() -> asyncpg.Pool:
    """Return the live pool. Raises if `init_pg_pool` was not called."""
    if _pool is None:
        raise RuntimeError(
            "Postgres pool is not initialised. Call init_pg_pool() in the "
            "FastAPI lifespan before using any Postgres-backed repository."
        )
    return _pool
