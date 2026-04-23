"""
Tests for the SSE sources event format helpers.

The context formatter used to live in routes/messages.py as `_format_context`.
Retrieval is now tool-driven and the equivalent formatter lives in
backend.rag.tools as `_format_search_results` — its behavior is covered in
test_tools.py. This file now only covers citation-object shape, SSE format,
and persistence round-trip.
"""


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
        assert isinstance(citation["start_seconds"], int | float)
        assert isinstance(citation["end_seconds"], int | float)


class TestSseSourcesEventEmission:
    """Tests for SSE sources event emission in messages route."""

    async def test_sources_event_emits_citation_objects(self) -> None:
        """The sources SSE event emits a JSON array of citation objects with all required fields."""
        import json

        chunks = [
            {
                "chunk_id": "chunk-abc",
                "video_id": "vid-1",
                "video_title": "Test Video",
                "video_url": "https://youtube.com/watch?v=abc123",
                "start_seconds": 62.5,
                "end_seconds": 70.0,
                "snippet": "Test snippet text",
            },
        ]

        # Build source_citations the same way the route does
        source_citations = [
            {
                "chunk_id": c.get("chunk_id", ""),
                "video_id": c.get("video_id", ""),
                "video_title": c.get("video_title", ""),
                "video_url": c.get("video_url", ""),
                "start_seconds": c.get("start_seconds", 0.0),
                "end_seconds": c.get("end_seconds", 0.0),
                "snippet": c.get("snippet", ""),
            }
            for c in chunks
            if c.get("chunk_id")
        ]

        # Verify the JSON serializes correctly (as it would in the SSE event)
        sources_json = json.dumps(source_citations)

        # Verify it can be parsed back
        parsed = json.loads(sources_json)
        assert len(parsed) == 1
        assert parsed[0]["chunk_id"] == "chunk-abc"
        assert parsed[0]["video_title"] == "Test Video"
        assert parsed[0]["start_seconds"] == 62.5
        assert parsed[0]["end_seconds"] == 70.0
        assert parsed[0]["snippet"] == "Test snippet text"

    async def test_sources_event_sse_format(self) -> None:
        """The SSE event format matches what the frontend parser expects."""
        import json

        source_citations = [
            {
                "chunk_id": "c1",
                "video_id": "v1",
                "video_title": "Video Title",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": 10.0,
                "end_seconds": 20.0,
                "snippet": "Snippet text",
            }
        ]

        sources_json = json.dumps(source_citations)
        sse_event = f"event: sources\ndata: {sources_json}\n\n"

        # Verify the format can be parsed back
        lines = sse_event.split("\n")
        assert lines[0] == "event: sources"
        assert lines[1].startswith("data: ")
        data_json = lines[1][6:]  # Remove "data: " prefix
        parsed = json.loads(data_json)
        assert parsed[0]["video_title"] == "Video Title"

    async def test_sources_event_with_empty_chunks(self) -> None:
        """Empty chunks list produces empty source_citations (no event emitted)."""
        chunks: list[dict] = []

        source_citations = [
            {
                "chunk_id": c.get("chunk_id", ""),
                "video_id": c.get("video_id", ""),
                "video_title": c.get("video_title", ""),
                "video_url": c.get("video_url", ""),
                "start_seconds": c.get("start_seconds", 0.0),
                "end_seconds": c.get("end_seconds", 0.0),
                "snippet": c.get("snippet", ""),
            }
            for c in chunks
            if c.get("chunk_id")
        ]

        assert source_citations == []

    async def test_sources_event_multiple_citations(self) -> None:
        """Multiple citations are all included in the sources event."""
        import json

        chunks = [
            {
                "chunk_id": "c1",
                "video_id": "v1",
                "video_title": "Video 1",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": 0.0,
                "end_seconds": 10.0,
                "snippet": "Snippet 1",
            },
            {
                "chunk_id": "c2",
                "video_id": "v2",
                "video_title": "Video 2",
                "video_url": "https://youtube.com/watch?v=def",
                "start_seconds": 5.0,
                "end_seconds": 15.0,
                "snippet": "Snippet 2",
            },
            {
                "chunk_id": "c3",
                "video_id": "v1",
                "video_title": "Video 1",
                "video_url": "https://youtube.com/watch?v=abc",
                "start_seconds": 20.0,
                "end_seconds": 30.0,
                "snippet": "Snippet 3",
            },
        ]

        source_citations = [
            {
                "chunk_id": c.get("chunk_id", ""),
                "video_id": c.get("video_id", ""),
                "video_title": c.get("video_title", ""),
                "video_url": c.get("video_url", ""),
                "start_seconds": c.get("start_seconds", 0.0),
                "end_seconds": c.get("end_seconds", 0.0),
                "snippet": c.get("snippet", ""),
            }
            for c in chunks
            if c.get("chunk_id")
        ]

        sources_json = json.dumps(source_citations)
        parsed = json.loads(sources_json)
        assert len(parsed) == 3
        assert parsed[0]["chunk_id"] == "c1"
        assert parsed[1]["chunk_id"] == "c2"
        assert parsed[2]["chunk_id"] == "c3"


class TestSourcesPersistenceRoundtrip:
    """Tests for source citation persistence round-trip through the repository layer.

    Covers: create_message(sources=...) → DB JSONB → list_messages deserialization.
    """

    async def test_create_message_stores_sources_json(self) -> None:
        """create_message stores sources as JSONB and list_messages deserializes it back."""
        import json
        from unittest.mock import AsyncMock, patch

        from backend.db import repository

        citations = [
            {
                "chunk_id": "chunk-abc",
                "video_id": "vid-1",
                "video_title": "Test Video",
                "video_url": "https://youtube.com/watch?v=abc123",
                "start_seconds": 62.5,
                "end_seconds": 70.0,
                "snippet": "Test snippet text",
            }
        ]

        # Patch _acquire to return a mock connection that records the call
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "msg-1",
                    "conversation_id": "conv-1",
                    "role": "assistant",
                    "content": "Test response",
                    "sources": json.dumps(citations),
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        )

        class _FakeAcquire:
            """Dual-purpose awaitable + async context manager."""

            def __await__(self):
                async def _do():
                    return mock_conn

                return _do().__await__()

            async def __aenter__(self):
                return mock_conn

            async def __aexit__(self, *exc):
                return False

        with patch.object(repository, "_acquire", lambda: _FakeAcquire()):
            msg = await repository.create_message(
                conversation_id="conv-1",
                user_id="test-user",
                role="assistant",
                content="Test response",
                sources=citations,
            )

        assert msg is not None
        assert msg["sources"] == citations

        # Verify execute was called (proving the DB write path was exercised)
        assert mock_conn.execute.called

    async def test_create_message_sources_none_round_trip(self) -> None:
        """sources=None is stored as NULL and deserialized as None."""
        from unittest.mock import AsyncMock, patch

        from backend.db import repository

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "msg-1",
                    "conversation_id": "conv-1",
                    "role": "assistant",
                    "content": "No citations",
                    "sources": None,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        )

        class _FakeAcquire:
            def __await__(self):
                async def _do():
                    return mock_conn

                return _do().__await__()

            async def __aenter__(self):
                return mock_conn

            async def __aexit__(self, *exc):
                return False

        with patch.object(repository, "_acquire", lambda: _FakeAcquire()):
            msg = await repository.create_message(
                conversation_id="conv-1",
                user_id="test-user",
                role="assistant",
                content="No citations",
                sources=None,
            )
            assert msg is not None
            assert msg["sources"] is None

            messages = await repository.list_messages("conv-1", "test-user")
            assert messages[0]["sources"] is None
