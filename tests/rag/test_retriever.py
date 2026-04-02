"""Tests for the cosine similarity retriever."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

# Ensure the app/backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app"))


def _make_chunk(chunk_id: str, video_id: str, content: str, embedding: list) -> dict:
    return {
        "id": chunk_id,
        "video_id": video_id,
        "content": content,
        "embedding": embedding,
    }


# ---------------------------------------------------------------------------
# min_score filtering tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_filters_below_min_score():
    """Chunks whose cosine similarity is below min_score must be excluded."""
    query = [1.0, 0.0, 0.0, 0.0]
    vec_a = [1.0, 0.0, 0.0, 0.0]  # similarity ≈ 1.0 — above threshold
    vec_b = [0.0, 1.0, 0.0, 0.0]  # similarity ≈ 0.0 — below threshold

    chunks = [
        _make_chunk("c1", "v1", "relevant content", vec_a),
        _make_chunk("c2", "v1", "irrelevant content", vec_b),
    ]

    with patch("backend.rag.retriever.repository") as mock_repo:
        mock_repo.list_chunks = AsyncMock(return_value=chunks)
        mock_repo.get_video = AsyncMock(return_value={"title": "Test Video"})

        from backend.rag import retriever

        results = await retriever.retrieve(query, k=5, min_score=0.5)

    assert len(results) == 1
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["score"] >= 0.5


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_all_below_threshold():
    """If every chunk is below min_score, retrieve() must return []."""
    query = [1.0, 0.0, 0.0, 0.0]
    vec = [0.0, 1.0, 0.0, 0.0]  # orthogonal → similarity 0.0

    chunks = [_make_chunk("c1", "v1", "content", vec)]

    with patch("backend.rag.retriever.repository") as mock_repo:
        mock_repo.list_chunks = AsyncMock(return_value=chunks)

        from backend.rag import retriever

        results = await retriever.retrieve(query, k=5, min_score=0.5)

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_includes_chunk_at_or_above_threshold():
    """A chunk with score == min_score is not below threshold and must be included."""
    query = [1.0, 0.0]
    vec = [1.0, 0.0]  # similarity = 1.0 exactly

    chunks = [_make_chunk("c1", "v1", "content", vec)]

    with patch("backend.rag.retriever.repository") as mock_repo:
        mock_repo.list_chunks = AsyncMock(return_value=chunks)
        mock_repo.get_video = AsyncMock(return_value={"title": "T"})

        from backend.rag import retriever

        # score == 1.0 >= min_score 1.0, so NOT skipped
        results = await retriever.retrieve(query, k=5, min_score=1.0)

    assert len(results) == 1


@pytest.mark.asyncio
async def test_retrieve_empty_db_returns_empty():
    """Empty DB must short-circuit to [] without touching NumPy."""
    with patch("backend.rag.retriever.repository") as mock_repo:
        mock_repo.list_chunks = AsyncMock(return_value=[])

        from backend.rag import retriever

        results = await retriever.retrieve([1.0, 0.0], k=5)

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_respects_k_limit():
    """retrieve() must not return more than k results."""
    query = [1.0, 0.0, 0.0, 0.0]
    chunks = [
        _make_chunk(f"c{i}", "v1", f"content {i}", [1.0, 0.0, 0.0, 0.0])
        for i in range(10)
    ]

    with patch("backend.rag.retriever.repository") as mock_repo:
        mock_repo.list_chunks = AsyncMock(return_value=chunks)
        mock_repo.get_video = AsyncMock(return_value={"title": "Vid"})

        from backend.rag import retriever

        results = await retriever.retrieve(query, k=3, min_score=0.0)

    assert len(results) <= 3


@pytest.mark.asyncio
async def test_retrieve_results_sorted_descending():
    """Results must be sorted by score descending."""
    query = [1.0, 0.0, 0.0, 0.0]
    # c1: perfect match, c2: partial match
    chunks = [
        _make_chunk("c1", "v1", "best", [1.0, 0.0, 0.0, 0.0]),
        _make_chunk("c2", "v1", "partial", [0.7, 0.7, 0.0, 0.0]),
    ]

    with patch("backend.rag.retriever.repository") as mock_repo:
        mock_repo.list_chunks = AsyncMock(return_value=chunks)
        mock_repo.get_video = AsyncMock(return_value={"title": "Vid"})

        from backend.rag import retriever

        results = await retriever.retrieve(query, k=5, min_score=0.0)

    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]


# ---------------------------------------------------------------------------
# _cosine_similarity_batch unit tests (zero-norm edge cases)
# ---------------------------------------------------------------------------


def test_cosine_zero_query_returns_zeros():
    """Zero-norm query must return all-zeros, not NaN."""
    from backend.rag.retriever import _cosine_similarity_batch

    query = np.zeros(4, dtype=np.float32)
    matrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
    result = _cosine_similarity_batch(query, matrix)

    assert np.all(result == 0.0)
    assert not np.any(np.isnan(result))


def test_cosine_zero_matrix_row_returns_zero_for_that_row():
    """Zero-norm row in matrix must not produce NaN."""
    from backend.rag.retriever import _cosine_similarity_batch

    query = np.array([1, 0, 0, 0], dtype=np.float32)
    matrix = np.array([[0, 0, 0, 0], [1, 0, 0, 0]], dtype=np.float32)
    result = _cosine_similarity_batch(query, matrix)

    assert not np.any(np.isnan(result))
    assert result[1] == pytest.approx(1.0)


def test_cosine_identical_vectors_returns_one():
    """Identical non-zero vectors must have cosine similarity 1.0."""
    from backend.rag.retriever import _cosine_similarity_batch

    v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    matrix = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    result = _cosine_similarity_batch(v, matrix)

    assert result[0] == pytest.approx(1.0, abs=1e-6)


def test_cosine_orthogonal_vectors_returns_zero():
    """Orthogonal vectors must have cosine similarity 0.0."""
    from backend.rag.retriever import _cosine_similarity_batch

    query = np.array([1.0, 0.0], dtype=np.float32)
    matrix = np.array([[0.0, 1.0]], dtype=np.float32)
    result = _cosine_similarity_batch(query, matrix)

    assert result[0] == pytest.approx(0.0, abs=1e-6)
