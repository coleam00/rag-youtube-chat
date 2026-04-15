"""
Tests for the retriever embedding cache.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.rag import retriever


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset module-level cache before each test."""
    retriever._cached_chunks = None
    retriever._cached_matrix = None
    retriever._cache_valid = False
    yield
    retriever._cached_chunks = None
    retriever._cached_matrix = None
    retriever._cache_valid = False


async def test_cache_populated_on_first_retrieve():
    """First retrieve() call loads and caches the embedding matrix."""
    fake_chunks = [
        {"id": "c1", "video_id": "v1", "content": "hello", "embedding": [0.1] * 1536, "chunk_index": 0},
        {"id": "c2", "video_id": "v1", "content": "world", "embedding": [0.2] * 1536, "chunk_index": 1},
    ]
    with patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list, \
         patch("backend.rag.retriever.repository.get_video", new_callable=AsyncMock) as mock_get_video:
        mock_list.return_value = fake_chunks
        mock_get_video.return_value = {"id": "v1", "title": "Test Video"}
        results = await retriever.retrieve(query_embedding=[0.1] * 1536, k=5)

    # list_chunks should have been called once (to populate cache)
    assert mock_list.call_count == 1
    assert len(results) == 2
    assert retriever._cache_valid is True
    assert retriever._cached_chunks == fake_chunks


async def test_cache_used_on_subsequent_retrieve():
    """Second retrieve() call uses cache without calling list_chunks()."""
    fake_chunks = [
        {"id": "c1", "video_id": "v1", "content": "hello", "embedding": [0.1] * 1536, "chunk_index": 0},
    ]
    with patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list, \
         patch("backend.rag.retriever.repository.get_video", new_callable=AsyncMock) as mock_get_video:
        mock_list.return_value = fake_chunks
        mock_get_video.return_value = {"id": "v1", "title": "Test Video"}
        # First call — populates cache
        await retriever.retrieve(query_embedding=[0.1] * 1536, k=5)
        # Second call — should use cache
        await retriever.retrieve(query_embedding=[0.1] * 1536, k=5)

    # list_chunks should have been called only once
    assert mock_list.call_count == 1


async def test_cache_invalidated_after_refresh():
    """refresh_embedding_cache() clears and rebuilds the cache."""
    fake_chunks = [
        {"id": "c1", "video_id": "v1", "content": "hello", "embedding": [0.1] * 1536, "chunk_index": 0},
    ]
    new_chunks = [
        {"id": "c1", "video_id": "v1", "content": "hello", "embedding": [0.1] * 1536, "chunk_index": 0},
        {"id": "c2", "video_id": "v1", "content": "world", "embedding": [0.2] * 1536, "chunk_index": 1},
    ]
    with patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list, \
         patch("backend.rag.retriever.repository.get_video", new_callable=AsyncMock) as mock_get_video:
        mock_list.return_value = fake_chunks
        mock_get_video.return_value = {"id": "v1", "title": "Test Video"}
        # Populate cache
        await retriever.retrieve(query_embedding=[0.1] * 1536, k=5)
        assert retriever._cache_valid is True

        # Switch return value for refresh
        mock_list.return_value = new_chunks
        # Refresh cache
        await retriever.refresh_embedding_cache()

    assert retriever._cache_valid is True
    assert len(retriever._cached_chunks) == 2


async def test_cache_cleared_after_clear():
    """clear_embedding_cache() marks cache invalid without rebuilding."""
    fake_chunks = [
        {"id": "c1", "video_id": "v1", "content": "hello", "embedding": [0.1] * 1536, "chunk_index": 0},
    ]
    with patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list, \
         patch("backend.rag.retriever.repository.get_video", new_callable=AsyncMock) as mock_get_video:
        mock_list.return_value = fake_chunks
        mock_get_video.return_value = {"id": "v1", "title": "Test Video"}
        # Populate cache
        await retriever.retrieve(query_embedding=[0.1] * 1536, k=5)
        assert retriever._cache_valid is True

        # Clear cache
        retriever.clear_embedding_cache()

    assert retriever._cache_valid is False
    # _cached_chunks is NOT nulled — it is retained until next retrieve() rebuilds
    assert retriever._cached_chunks == fake_chunks


async def test_retrieve_returns_empty_when_no_chunks():
    """Empty DB returns [] without errors."""
    with patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []
        results = await retriever.retrieve(query_embedding=[0.1] * 1536, k=5)

    assert results == []
    assert retriever._cache_valid is True
    assert retriever._cached_chunks == []