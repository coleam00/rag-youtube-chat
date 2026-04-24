"""Tests for backend.rag.reranker — cross-encoder reranking."""

from __future__ import annotations

from unittest.mock import patch, Mock, AsyncMock

import pytest

from backend.rag.reranker import rerank_chunks


class TestRerankChunks:
    """Unit tests for rerank_chunks function."""

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self) -> None:
        result = await rerank_chunks("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_top_k_zero_returns_empty(self) -> None:
        chunks = [{"content": "test"}]
        result = await rerank_chunks("query", chunks, top_k=0)
        assert result == []

    @pytest.mark.asyncio
    async def test_top_k_negative_returns_empty(self) -> None:
        chunks = [{"content": "test"}]
        result = await rerank_chunks("query", chunks, top_k=-1)
        assert result == []

    @pytest.mark.asyncio
    async def test_scores_attached_and_sorted_descending(self) -> None:
        fake_scores = [0.1, 0.9, 0.5]
        chunks = [
            {"content": "low"},
            {"content": "high"},
            {"content": "mid"},
        ]

        with patch("backend.rag.reranker._get_cross_encoder") as mock_get:
            mock_model = Mock()
            mock_model.predict.return_value = fake_scores
            mock_get.return_value = mock_model

            result = await rerank_chunks("query", chunks, top_k=3)

            assert len(result) == 3
            # Check cross_encoder_score is attached
            assert all("cross_encoder_score" in c for c in result)
            # Check descending order: high(0.9) > mid(0.5) > low(0.1)
            scores = [c["cross_encoder_score"] for c in result]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_respects_top_k_slice(self) -> None:
        chunks = [{"content": f"doc{i}"} for i in range(10)]
        fake_scores = [float(i) for i in range(10)]  # 0.0 to 9.0

        with patch("backend.rag.reranker._get_cross_encoder") as mock_get:
            mock_model = Mock()
            mock_model.predict.return_value = fake_scores
            mock_get.return_value = mock_model

            result = await rerank_chunks("query", chunks, top_k=3)
            assert len(result) == 3
            # highest scores are 9, 8, 7 → chunks at indices 9, 8, 7
            assert result[0]["content"] == "doc9"
            assert result[1]["content"] == "doc8"
            assert result[2]["content"] == "doc7"

    @pytest.mark.asyncio
    async def test_handles_chunks_without_content_field(self) -> None:
        fake_scores = [0.5]
        chunks = [{"other_field": "value"}]  # no "content" key

        with patch("backend.rag.reranker._get_cross_encoder") as mock_get:
            mock_model = Mock()
            mock_model.predict.return_value = fake_scores
            mock_get.return_value = mock_model

            # Should not raise — uses c.get("content", "")
            result = await rerank_chunks("query", chunks, top_k=1)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_model_predict_called_with_correct_pairs(self) -> None:
        chunks = [{"content": "doc1"}, {"content": "doc2"}]
        captured_pairs: list[tuple[str, str]] = []

        def capture_predict(pairs):
            captured_pairs.extend(pairs)
            return [0.1, 0.2]

        with patch("backend.rag.reranker._get_cross_encoder") as mock_get:
            mock_model = Mock()
            mock_model.predict.side_effect = capture_predict
            mock_get.return_value = mock_model

            await rerank_chunks("my query", chunks, top_k=2)

            assert captured_pairs == [("my query", "doc1"), ("my query", "doc2")]

    @pytest.mark.asyncio
    async def test_original_chunks_not_mutated(self) -> None:
        chunks = [{"content": "orig", "id": "c1"}]
        fake_scores = [0.9]

        with patch("backend.rag.reranker._get_cross_encoder") as mock_get:
            mock_model = Mock()
            mock_model.predict.return_value = fake_scores
            mock_get.return_value = mock_model

            result = await rerank_chunks("query", chunks, top_k=1)
            # result should have cross_encoder_score, original chunk should not
            assert "cross_encoder_score" in result[0]
            assert "cross_encoder_score" not in chunks[0]

    @pytest.mark.asyncio
    async def test_cross_encoder_score_is_float_and_sortable(self) -> None:
        chunks = [{"content": f"doc{i}"} for i in range(5)]
        fake_scores = [0.3, 0.1, 0.9, 0.4, 0.2]

        with patch("backend.rag.reranker._get_cross_encoder") as mock_get:
            mock_model = Mock()
            mock_model.predict.return_value = fake_scores
            mock_get.return_value = mock_model

            result = await rerank_chunks("query", chunks, top_k=5)

            for c in result:
                assert isinstance(c["cross_encoder_score"], float)
            # Scores should be sortable (no NaN, no None)
            scores = [c["cross_encoder_score"] for c in result]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_more_chunks_than_top_k_returns_top_k_only(self) -> None:
        """When there are more chunks than top_k, only top_k are returned."""
        chunks = [{"content": f"doc{i}"} for i in range(20)]
        fake_scores = [float(i) for i in range(20)]  # 0.0 to 19.0

        with patch("backend.rag.reranker._get_cross_encoder") as mock_get:
            mock_model = Mock()
            mock_model.predict.return_value = fake_scores
            mock_get.return_value = mock_model

            result = await rerank_chunks("query", chunks, top_k=5)
            assert len(result) == 5
            # Top 5 scores are 19, 18, 17, 16, 15
            assert result[0]["content"] == "doc19"
            assert result[4]["content"] == "doc15"
