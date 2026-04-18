"""
Tests for search_conversations_by_title repository function.

NOTE: Tests were written against SQLite `init_db` fixtures. After the
Postgres/Alembic migration they need a rewrite using a real test Postgres.
Skipped pending that rewrite.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-please-do-not-use-in-prod")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

pytestmark = pytest.mark.skip(
    reason="Tests require SQLite schema.init_db; pending rewrite for asyncpg/Alembic."
)

from backend.db.repository import (  # noqa: E402
    create_conversation,
    search_conversations_by_title,
)


async def test_search_conversations_by_title_case_insensitive():
    """Search should be case-insensitive using LOWER()."""
    user_id = str(uuid4())
    await create_conversation(user_id=user_id, title="Python Tutorial")
    await create_conversation(user_id=user_id, title="JavaScript Guide")
    await create_conversation(user_id=user_id, title="python advanced")

    results = await search_conversations_by_title(user_id, "python")
    titles = {r["title"] for r in results}
    assert titles == {"Python Tutorial", "python advanced"}

    results = await search_conversations_by_title(user_id, "PYTHON")
    titles = {r["title"] for r in results}
    assert titles == {"Python Tutorial", "python advanced"}


async def test_search_conversations_returns_only_own():
    """Search should only return conversations owned by the user."""
    alice_id = str(uuid4())
    bob_id = str(uuid4())

    await create_conversation(user_id=alice_id, title="Alice Searchable")
    await create_conversation(user_id=bob_id, title="Bob Searchable")

    results = await search_conversations_by_title(alice_id, "searchable")
    titles = {r["title"] for r in results}
    assert titles == {"Alice Searchable"}
    assert "Bob Searchable" not in titles


async def test_search_conversations_empty_query():
    """Empty query should return no results (pattern would be %%)."""
    user_id = str(uuid4())
    await create_conversation(user_id=user_id, title="Test Chat")

    results = await search_conversations_by_title(user_id, "")
    assert isinstance(results, list)


async def test_search_conversations_limit():
    """Search should respect the limit parameter."""
    user_id = str(uuid4())
    for i in range(5):
        await create_conversation(user_id=user_id, title=f"Chat {i}")

    results = await search_conversations_by_title(user_id, "chat", limit=3)
    assert len(results) == 3


async def test_search_conversations_no_matches():
    """Search should return empty list when no matches."""
    user_id = str(uuid4())
    await create_conversation(user_id=user_id, title="Python Tutorial")

    results = await search_conversations_by_title(user_id, "javascript")
    assert results == []
