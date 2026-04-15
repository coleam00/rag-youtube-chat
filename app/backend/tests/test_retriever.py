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
        {
            "id": "c1",
            "video_id": "v1",
            "content": "hello",
            "embedding": [0.1] * 1536,
            "chunk_index": 0,
        },
        {
            "id": "c2",
            "video_id": "v1",
            "content": "world",
            "embedding": [0.2] * 1536,
            "chunk_index": 1,
        },
    ]
    with (
        patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list,
        patch(
            "backend.rag.retriever.repository.get_video", new_callable=AsyncMock
        ) as mock_get_video,
    ):
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
        {
            "id": "c1",
            "video_id": "v1",
            "content": "hello",
            "embedding": [0.1] * 1536,
            "chunk_index": 0,
        },
    ]
    with (
        patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list,
        patch(
            "backend.rag.retriever.repository.get_video", new_callable=AsyncMock
        ) as mock_get_video,
    ):
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
        {
            "id": "c1",
            "video_id": "v1",
            "content": "hello",
            "embedding": [0.1] * 1536,
            "chunk_index": 0,
        },
    ]
    new_chunks = [
        {
            "id": "c1",
            "video_id": "v1",
            "content": "hello",
            "embedding": [0.1] * 1536,
            "chunk_index": 0,
        },
        {
            "id": "c2",
            "video_id": "v1",
            "content": "world",
            "embedding": [0.2] * 1536,
            "chunk_index": 1,
        },
    ]
    with (
        patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list,
        patch(
            "backend.rag.retriever.repository.get_video", new_callable=AsyncMock
        ) as mock_get_video,
    ):
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
        {
            "id": "c1",
            "video_id": "v1",
            "content": "hello",
            "embedding": [0.1] * 1536,
            "chunk_index": 0,
        },
    ]
    with (
        patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list,
        patch(
            "backend.rag.retriever.repository.get_video", new_callable=AsyncMock
        ) as mock_get_video,
    ):
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


# ---------------------------------------------------------------------------
# Internal helper edge case tests
# ---------------------------------------------------------------------------


def test_cosine_similarity_zero_query_vector():
    """Zero-norm query returns all-zero scores (doesn't crash)."""
    import numpy as np

    from backend.rag.retriever import _cosine_similarity_batch

    matrix = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
    query = np.array([0.0, 0.0], dtype=np.float32)

    result = _cosine_similarity_batch(query, matrix)

    assert result.shape == (2,)
    assert np.all(result == 0.0)


def test_cosine_similarity_zero_norm_matrix_row():
    """Matrix rows with zero norm are clamped and don't cause divide-by-zero."""
    import numpy as np

    from backend.rag.retriever import _cosine_similarity_batch

    matrix = np.array([[0.0, 0.0], [0.1, 0.2]], dtype=np.float32)  # first row is zero-norm
    query = np.array([0.1, 0.2], dtype=np.float32)

    result = _cosine_similarity_batch(query, matrix)

    assert result.shape == (2,)
    assert not np.any(np.isnan(result))
    assert result[0] == 0.0  # zero-norm row gets 0 score


def test_cosine_similarity_normal_case():
    """Normal vectors return correct cosine similarities."""
    import numpy as np

    from backend.rag.retriever import _cosine_similarity_batch

    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)  # [1,0] and [0,1]
    query = np.array([1.0, 0.0], dtype=np.float32)  # matches [1,0]

    result = _cosine_similarity_batch(query, matrix)

    assert result[0] > result[1]  # [1,0] is closer to [1,0] than [0,1]


# ---------------------------------------------------------------------------
# Concurrent access and error path tests
# ---------------------------------------------------------------------------


async def test_concurrent_retrieve_calls_do_not_error():
    """Multiple concurrent retrieve() calls during cold cache all complete."""
    import asyncio

    fake_chunks = [
        {
            "id": f"c{i}",
            "video_id": "v1",
            "content": f"chunk {i}",
            "embedding": [0.1] * 1536,
            "chunk_index": i,
        }
        for i in range(10)
    ]
    with (
        patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list,
        patch("backend.rag.retriever.repository.get_video", new_callable=AsyncMock) as mock_get_video,
    ):
        mock_list.return_value = fake_chunks
        mock_get_video.return_value = {"id": "v1", "title": "Test Video"}

        # Fire 10 concurrent retrieve calls with a cold cache
        results = await asyncio.gather(*[
            retriever.retrieve(query_embedding=[0.1] * 1536, k=5)
            for _ in range(10)
        ])

        # All calls should succeed
        assert len(results) == 10
        for r in results:
            assert len(r) == 5
        # list_chunks should have been called exactly once (first to init, rest use cache)
        assert mock_list.call_count == 1


async def test_retrieve_propagates_db_errors():
    """If list_chunks() fails, retrieve() raises the exception."""
    with patch("backend.rag.retriever.repository.list_chunks", new_callable=AsyncMock) as mock_list:
        mock_list.side_effect = ConnectionError("DB unavailable")

        with pytest.raises(ConnectionError):
            await retriever.retrieve(query_embedding=[0.1] * 1536, k=5)
