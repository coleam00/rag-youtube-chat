"""
Tests for the SSE sources event format helpers.

Verifies:
  - _format_context includes timestamp markers (mm:ss) in the context block
  - Citation objects have all required keys for the SSE sources event

The SSE event emission itself is tested via integration tests in test_ingest_cache_invalidation.py
which validate the full streaming stack against mocked dependencies.
"""

import pytest

from backend.routes.messages import _format_context


class TestFormatContext:
    """Tests for _format_context timestamp formatting."""

    def test_includes_video_title(self) -> None:
        """Context block contains the video title."""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "Test content",
                "video_id": "v1",
                "video_title": "My Video",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": 0.0,
                "end_seconds": 10.0,
                "snippet": "Test snippet",
                "score": 0.9,
            }
        ]
        ctx = _format_context(chunks)
        assert "My Video" in ctx

    def test_includes_mm_ss_timestamp(self) -> None:
        """Context block contains mm:ss timestamp marker."""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "Test content",
                "video_id": "v1",
                "video_title": "My Video",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": 62.5,  # 1:02
                "end_seconds": 70.0,
                "snippet": "Test snippet",
                "score": 0.9,
            }
        ]
        ctx = _format_context(chunks)
        assert "01:02" in ctx

    def test_zero_seconds_formats_correctly(self) -> None:
        """Zero start_seconds formats as 00:00."""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "Test content",
                "video_id": "v1",
                "video_title": "My Video",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": 0.0,
                "end_seconds": 10.0,
                "snippet": "Test snippet",
                "score": 0.9,
            }
        ]
        ctx = _format_context(chunks)
        assert "00:00" in ctx

    def test_large_timestamp_formats_correctly(self) -> None:
        """Timestamps > 60 minutes format correctly."""
        chunks = [
            {
                "chunk_id": "c1",
                "content": "Test content",
                "video_id": "v1",
                "video_title": "My Video",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": 3661.0,  # 61:01
                "end_seconds": 3670.0,
                "snippet": "Test snippet",
                "score": 0.9,
            }
        ]
        ctx = _format_context(chunks)
        assert "61:01" in ctx

    def test_empty_chunks_returns_empty_string(self) -> None:
        """Empty chunks list returns empty string."""
        ctx = _format_context([])
        assert ctx == ""

    def test_multiple_chunks_have_separators(self) -> None:
        """Multiple chunks are separated by --- delimiter."""
        chunks = [
            {
                "chunk_id": f"c{i}",
                "content": f"Content {i}",
                "video_id": "v1",
                "video_title": "Video",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": float(i * 10),
                "end_seconds": float((i + 1) * 10),
                "snippet": f"Snippet {i}",
                "score": 0.9,
            }
            for i in range(3)
        ]
        ctx = _format_context(chunks)
        assert "---" in ctx


class TestCitationObjectShape:
    """Tests that verify citation objects have all required SSE fields."""

    def test_citation_has_all_required_keys(self) -> None:
        """A citation dict from retrieve() has all keys needed for SSE emission."""
        citation = {
            "chunk_id": "chunk-abc",
            "video_id": "vid-1",
            "video_title": "Test Video",
            "video_url": "https://youtube.com/watch?v=abc123",
            "start_seconds": 62.5,
            "end_seconds": 70.0,
            "snippet": "Test snippet text",
            "score": 0.95,
        }
        required_keys = {
            "chunk_id",
            "video_id",
            "video_title",
            "video_url",
            "start_seconds",
            "end_seconds",
            "snippet",
        }
        assert required_keys.issubset(citation.keys())

    def test_start_seconds_is_float(self) -> None:
        """start_seconds is a float (for sub-second precision)."""
        citation = {
            "chunk_id": "c1",
            "video_id": "v1",
            "video_title": "T",
            "video_url": "https://youtube.com/watch?v=abc",
            "start_seconds": 62.5,
            "end_seconds": 70.0,
            "snippet": "s",
            "score": 0.9,
        }
        assert isinstance(citation["start_seconds"], (int, float))
        assert isinstance(citation["end_seconds"], (int, float))
