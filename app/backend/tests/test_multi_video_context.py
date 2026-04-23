"""
Integration tests for multi-video context behavior.

Verifies that when a broad question retrieves chunks dominated by one video,
the per-video cap (RETRIEVAL_MAX_PER_VIDEO) still produces context from
at least two videos — enabling cross-video synthesis.

Covers issue flagged in pass-1 validation: "broad question with mostly one
video in top retrieval produces context from at least two videos".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.auth.dependencies import get_current_user
from backend.config import RETRIEVAL_TOP_K
from backend.main import app


@pytest.fixture(autouse=True)
def stub_user():
    """Satisfy the auth gate with a fake user."""
    stub = {"id": "test-user-id", "email": "test@example.com"}
    app.dependency_overrides[get_current_user] = lambda: stub
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def test_per_video_cap_preserves_multi_video_context():
    """When one video dominates top-K retrieval, cap still leaves ≥2 videos in context.

    Scenario: RETRIEVAL_TOP_K=5, RETRIEVAL_MAX_PER_VIDEO=3.
    Retrieval returns 4 chunks from v1 + 1 chunk from v2.
    After applying per-video cap (3 per video), we should still have
    chunks from at least 2 distinct videos in the context.
    """
    # Chunks returned by retrieve_hybrid: 4 from v1, 1 from v2
    dominant_video_chunks = [
        {
            "chunk_id": f"c{i}",
            "video_id": "v1",
            "video_title": "Video One",
            "video_url": "https://youtube.com/watch?v=v1",
            "start_seconds": float(i * 10),
            "end_seconds": float((i + 1) * 10),
            "content": f"Content chunk {i} from video one",
            "snippet": f"Snippet {i} from video one",
        }
        for i in range(4)
    ]
    minority_video_chunk = [
        {
            "chunk_id": "c99",
            "video_id": "v2",
            "video_title": "Video Two",
            "video_url": "https://youtube.com/watch?v=v2",
            "start_seconds": 5.0,
            "end_seconds": 15.0,
            "content": "Content from video two",
            "snippet": "Snippet from video two",
        }
    ]
    all_chunks = dominant_video_chunks + minority_video_chunk

    mock_conv = {"id": "conv-123", "user_id": "test-user-id", "title": "Test"}

    with (
        patch(
            "backend.routes.messages.repository.get_conversation",
            new_callable=AsyncMock,
            return_value=mock_conv,
        ),
        patch(
            "backend.routes.messages.repository.create_message",
            new_callable=AsyncMock,
            return_value={"id": "msg-new", "role": "user", "content": "test"},
        ),
        patch(
            "backend.routes.messages.repository.list_messages",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "backend.routes.messages.embed_text",
            new_callable=AsyncMock,
            return_value=[0.1] * 1536,
        ),
        patch(
            "backend.routes.messages.retrieve_hybrid",
            new_callable=AsyncMock,
            return_value=all_chunks,
        ) as mock_retrieve,
        patch(
            "backend.routes.messages.stream_chat",
        ) as mock_stream_chat,
    ):
        # stream_chat yields one token then [DONE]
        async def fake_stream(*args, **kwargs):
            yield 'data: "Hello"\n\n'
            yield "data: [DONE]\n\n"

        mock_stream_chat.side_effect = fake_stream

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/conversations/conv-123/messages",
                json={"content": "Tell me about both topics"},
            )

        assert response.status_code == 200

        # Verify retrieve_hybrid was called with RETRIEVAL_TOP_K
        mock_retrieve.assert_called_once()
        call_kwargs = mock_retrieve.call_args.kwargs
        assert call_kwargs.get("top_k") == RETRIEVAL_TOP_K

        # Parse SSE response content to find the sources event
        # SSE format: "event: sources\ndata: <json>\n\n" before "data: [DONE]\n\n"
        content = response.text
        chunks_by_video: dict[str, int] = {}

        import json

        current_event: str | None = None
        current_data: str | None = None

        for line in content.split("\n"):
            if line.startswith("event: "):
                current_event = line[len("event: ") :]
            elif line.startswith("data: "):
                current_data = line[len("data: ") :]
                if current_event == "sources" and current_data not in ("[DONE]", ""):
                    try:
                        citations = json.loads(current_data)
                        if isinstance(citations, list):
                            for citation in citations:
                                vid = citation.get("video_id", "")
                                chunks_by_video[vid] = chunks_by_video.get(vid, 0) + 1
                    except json.JSONDecodeError:
                        pass
                current_event = None
                current_data = None
            elif line == "":
                # Empty line marks end of event
                current_event = None
                current_data = None

        # After per-video cap, we must still have chunks from at least 2 videos
        assert len(chunks_by_video) >= 2, (
            f"Expected ≥2 videos after per-video cap, got {chunks_by_video}"
        )
