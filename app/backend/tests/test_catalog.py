"""Tests for backend.rag.catalog — video catalog cache and prompt block builder."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from backend.rag import catalog

# ---------------------------------------------------------------------------
# get_catalog / invalidate_catalog
# ---------------------------------------------------------------------------


async def test_get_catalog_populates_cache() -> None:
    catalog._catalog_cache = None
    fake = [{"id": "1", "title": "T", "url": "https://youtube.com/watch?v=abc"}]
    with patch("backend.rag.catalog.repository.list_videos", new_callable=AsyncMock) as mock_lv:
        mock_lv.return_value = fake
        result = await catalog.get_catalog()
        mock_lv.assert_called_once()
        assert result == fake


async def test_get_catalog_uses_cache() -> None:
    fake = [{"id": "1", "title": "T", "url": "https://youtube.com/watch?v=abc"}]
    catalog._catalog_cache = fake
    with patch("backend.rag.catalog.repository.list_videos", new_callable=AsyncMock) as mock_lv:
        result = await catalog.get_catalog()
        mock_lv.assert_not_called()
        assert result is fake
    catalog._catalog_cache = None  # cleanup


def test_invalidate_catalog_clears_cache() -> None:
    catalog._catalog_cache = [{"id": "1"}]
    catalog.invalidate_catalog()
    assert catalog._catalog_cache is None


# ---------------------------------------------------------------------------
# build_catalog_block
# ---------------------------------------------------------------------------


def test_build_catalog_block_standard() -> None:
    videos = [{"title": "My Video", "url": "https://youtube.com/watch?v=abc"}]
    block = catalog.build_catalog_block(videos, "standard")
    assert block["type"] == "text"
    assert "My Video" in block["text"]
    assert "https://youtube.com/watch?v=abc" in block["text"]
    assert block["cache_control"] == {"type": "ephemeral"}


def test_build_catalog_block_extended() -> None:
    videos = [{"title": "My Video", "url": "https://youtube.com/watch?v=abc"}]
    block = catalog.build_catalog_block(videos, "extended")
    assert block["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_build_catalog_block_untitled_fallback() -> None:
    videos = [{"title": None, "url": "https://youtube.com/watch?v=abc"}]
    block = catalog.build_catalog_block(videos, "standard")
    assert "Untitled" in block["text"]


def test_build_catalog_block_numbering() -> None:
    videos = [
        {"title": "A", "url": "u1"},
        {"title": "B", "url": "u2"},
        {"title": "C", "url": "u3"},
    ]
    block = catalog.build_catalog_block(videos, "standard")
    assert "1. A" in block["text"]
    assert "2. B" in block["text"]
    assert "3. C" in block["text"]


# ---------------------------------------------------------------------------
# build_system_prompt integration
# ---------------------------------------------------------------------------


async def test_build_system_prompt_with_catalog() -> None:
    from backend.llm.openrouter import build_system_prompt

    fake = [{"title": "Vid", "url": "https://youtu.be/x"}]
    with (
        patch("backend.llm.openrouter.CATALOG_ENABLED", True),
        patch("backend.rag.catalog.get_catalog", new_callable=AsyncMock, return_value=fake),
    ):
        blocks = await build_system_prompt(max_tool_calls=6)
    assert len(blocks) == 2
    assert "cache_control" in blocks[-1]
    assert "cache_control" not in blocks[0]


async def test_build_system_prompt_without_catalog() -> None:
    from backend.llm.openrouter import build_system_prompt

    with patch("backend.llm.openrouter.CATALOG_ENABLED", False):
        blocks = await build_system_prompt(max_tool_calls=0)
    assert len(blocks) == 1
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


async def test_build_system_prompt_catalog_empty_library() -> None:
    from backend.llm.openrouter import build_system_prompt

    with (
        patch("backend.llm.openrouter.CATALOG_ENABLED", True),
        patch("backend.rag.catalog.get_catalog", new_callable=AsyncMock, return_value=[]),
    ):
        blocks = await build_system_prompt(max_tool_calls=6)
    # Empty library: no catalog block, cache anchor on base block
    assert len(blocks) == 1
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
