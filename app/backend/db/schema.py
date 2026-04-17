"""
Database schema definitions and migration utilities.

NOTE: This module is kept as a stub for backwards compatibility with tests.
The actual schema is now managed by Alembic migrations (alembic/versions/).
Tables are created via Postgres DDL, not via SQLite initialization.
"""

# DB_PATH and SQLite concepts removed during Postgres migration.


async def init_db() -> None:
    """Stub - schema is now managed by Alembic migrations.

    Kept for backwards compatibility with tests that reference this function.
    The actual database initialization happens via `alembic upgrade head`
    in the FastAPI lifespan, not via this function.
    """
    # No-op: schema is managed by Alembic, not by SQLite init.
    # Tests that reference this should be updated to use Postgres fixtures.
    pass
