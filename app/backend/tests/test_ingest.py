"""
Integration test for retriever cache invalidation on ingest.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
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


async def test_ingest_invalidates_retriever_cache():
    """POST /api/ingest invalidates and refreshes the retriever cache."""
    fake_video = {"id": "vid-123", "title": "Test Video", "description": "desc", "url": "https://youtu.be/x", "transcript": "transcript"}
    fake_chunks = [
        {"id": "c1", "video_id": "vid-123", "content": "hello", "embedding": [0.1] * 1536, "chunk_index": 0},
    ]

    with patch("backend.routes.ingest.repository.create_video", new_callable=AsyncMock) as mock_create_video, \
         patch("backend.routes.ingest.chunk_video", return_value=["hello"]) as mock_chunk, \
         patch("backend.routes.ingest.embed_batch", return_value=[[0.1] * 1536]) as mock_embed_batch, \
         patch("backend.routes.ingest.repository.create_chunk", new_callable=AsyncMock) as mock_create_chunk, \
         patch("backend.routes.ingest.refresh_embedding_cache", new_callable=AsyncMock) as mock_refresh:

        mock_create_video.return_value = fake_video
        mock_chunk.return_value = ["hello"]
        mock_embed_batch.return_value = [[0.1] * 1536]
        mock_create_chunk.return_value = None
        mock_refresh.return_value = None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/ingest",
                json={
                    "title": "Test Video",
                    "description": "desc",
                    "url": "https://youtu.be/x",
                    "transcript": "hello world this is a test",
                },
            )

        assert response.status_code == 200
        # refresh_embedding_cache must have been called after chunk creation
        mock_refresh.assert_called_once()