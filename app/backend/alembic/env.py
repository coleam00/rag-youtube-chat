"""
Alembic async migration environment.

Reads DATABASE_URL from backend.config and uses SQLAlchemy's async engine
to run migrations. This replaces the old `init_db()` / `init_users_schema()` /
`init_signup_attempts_schema()` pattern.
"""

import asyncio
from logging import getLogger

from backend.config import DATABASE_URL
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

logger = getLogger(__name__)


def _get_async_database_url(url: str) -> str:
    """Convert a postgresql:// URL to postgresql+asyncpg:// for SQLAlchemy async."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no database connection needed).

    Used for `alembic revision --autogenerate` and similar commands that
    don't need to connect to the DB.
    """
    url = DATABASE_URL or "postgresql://localhost/dynachat"
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an asyncpg-backed AsyncEngine.

    Creates a dedicated async engine for the migration run (kept separate
    from the app's main pool managed in postgres.py) so migrations are
    fully self-contained.
    """
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set; cannot run migrations. "
            "Set the env var or ensure docker-compose provides it."
        )

    async_url = _get_async_database_url(DATABASE_URL)
    engine = create_async_engine(async_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(_do_configure_and_run)

    await engine.dispose()
    logger.info("Alembic migrations complete.")


def _do_configure_and_run(connection) -> None:
    """Sync callback run inside the async connection's thread.

    SQLAlchemy's `run_sync` calls this in the async connection's execution
    context. We configure the Alembic context with the raw connection object
    (which is an AsyncConnection under the hood) so Alembic can use it directly.
    """
    context.configure(connection=connection, asynchronous=True)
    context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
