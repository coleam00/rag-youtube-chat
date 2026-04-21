"""
Regression tests for issue #89 — all chunks have start_seconds=0.0.

Verifies that the from-url ingest path, admin _fetch_chunks_and_embeddings,
and channel sync all pass real timestamp fields to create_chunk rather than
leaving them at the default 0.0.

Also covers issue #112: the /api/channels/sync?force=true backfill path,
which replaces chunks on videos ingested before the #89 fix landed.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-please-do-not-use-in-prod")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SUPADATA_API_KEY", "test-supadata-key")
os.environ.setdefault("YOUTUBE_CHANNEL_ID", "UC_testchannel")

from backend.auth.dependencies import get_current_admin, get_current_user
from backend.main import app


@pytest.fixture(autouse=True)
def bypass_auth():
    """Satisfy the auth gate with a stub user.

    /api/ingest and /api/channels/sync are admin-gated, so stub both
    get_current_user and get_current_admin — overriding only the former
    leaves the admin check active and returns 403.
    """
    stub_user = {"id": "test-user", "email": "t@t"}
    app.dependency_overrides[get_current_user] = lambda: stub_user
    app.dependency_overrides[get_current_admin] = lambda: stub_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_admin, None)


# ---------------------------------------------------------------------------
# Regression: from-url ingest stores real timestamps
# ---------------------------------------------------------------------------


async def test_ingest_from_url_stores_timestamps():
    """create_chunk must be called with non-zero timestamps when segments are present."""
    from httpx import ASGITransport, AsyncClient

    mock_video = {
        "id": "v-ts-1",
        "title": "Timestamp Test",
        "description": "desc",
        "url": "https://www.youtube.com/watch?v=ts1",
        "transcript": "Intro. Main content. Conclusion.",
    }

    fake_helper = AsyncMock(
        return_value={
            "youtube_video_id": "ts1",
            "title": "Timestamp Test",
            "description": "desc",
            "transcript": "Intro. Main content. Conclusion.",
            "segments": [
                {"start": 0.0, "end": 30.0, "text": "Intro."},
                {"start": 30.0, "end": 90.0, "text": "Main content."},
                {"start": 90.0, "end": 120.0, "text": "Conclusion."},
            ],
        }
    )

    chunk_dicts = [
        {"content": "Intro.", "start_seconds": 0.0, "end_seconds": 30.0, "snippet": "Intro."},
        {
            "content": "Main content.",
            "start_seconds": 30.0,
            "end_seconds": 90.0,
            "snippet": "Main content.",
        },
        {
            "content": "Conclusion.",
            "start_seconds": 90.0,
            "end_seconds": 120.0,
            "snippet": "Conclusion.",
        },
    ]

    with (
        patch("backend.routes.ingest.fetch_video_for_ingest", new=fake_helper),
        patch(
            "backend.routes.ingest.repository.create_video",
            new_callable=AsyncMock,
            return_value=mock_video,
        ),
        patch("backend.routes.ingest.chunk_video_timestamped", return_value=(chunk_dicts, False)),
        patch("backend.routes.ingest.embed_batch", return_value=[[0.1] * 3, [0.2] * 3, [0.3] * 3]),
        patch(
            "backend.routes.ingest.repository.create_chunk", new_callable=AsyncMock
        ) as mock_create_chunk,
        patch("backend.routes.ingest.retriever.invalidate_cache"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/ingest/from-url",
                json={"url": "https://www.youtube.com/watch?v=ts1"},
            )

    assert response.status_code == 200
    assert response.json()["chunks_created"] == 3

    # Verify timestamps
    calls = mock_create_chunk.call_args_list
    assert len(calls) == 3
    # First chunk must have start_seconds=0.0
    first_call_kwargs = calls[0].kwargs
    assert first_call_kwargs["start_seconds"] == 0.0
    assert first_call_kwargs["end_seconds"] == 30.0
    # Second chunk must have start_seconds=30.0 (not 0.0 — regression check)
    second_call_kwargs = calls[1].kwargs
    assert second_call_kwargs["start_seconds"] == 30.0
    assert second_call_kwargs["end_seconds"] == 90.0
    assert second_call_kwargs["snippet"] == "Main content."
    # Third chunk
    third_call_kwargs = calls[2].kwargs
    assert third_call_kwargs["start_seconds"] == 90.0


# ---------------------------------------------------------------------------
# Regression: fallback path still produces dicts (not plain strings)
# ---------------------------------------------------------------------------


async def test_ingest_from_url_fallback_stores_timestamps_when_no_segments():
    """When no segments are provided, chunk_video_fallback is used and timestamps are estimated."""
    from httpx import ASGITransport, AsyncClient

    mock_video = {
        "id": "v-ts-2",
        "title": "No Segments Video",
        "description": "desc",
        "url": "https://www.youtube.com/watch?v=nosegs",
        "transcript": " ".join(["word"] * 200),
    }

    fake_helper = AsyncMock(
        return_value={
            "youtube_video_id": "nosegs",
            "title": "No Segments Video",
            "description": "desc",
            "transcript": " ".join(["word"] * 200),
            "segments": [],  # no segments → fallback path
        }
    )

    fallback_chunk = {
        "content": "word word word",
        "start_seconds": 0.0,
        "end_seconds": 40.0,
        "snippet": "word word word",
    }

    with (
        patch("backend.routes.ingest.fetch_video_for_ingest", new=fake_helper),
        patch(
            "backend.routes.ingest.repository.create_video",
            new_callable=AsyncMock,
            return_value=mock_video,
        ),
        patch("backend.routes.ingest.chunk_video_fallback", return_value=([fallback_chunk], False)),
        patch("backend.routes.ingest.embed_batch", return_value=[[0.1] * 3]),
        patch(
            "backend.routes.ingest.repository.create_chunk", new_callable=AsyncMock
        ) as mock_create_chunk,
        patch("backend.routes.ingest.retriever.invalidate_cache"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/ingest/from-url",
                json={"url": "https://www.youtube.com/watch?v=nosegs"},
            )

    assert response.status_code == 200
    assert response.json()["chunks_created"] == 1

    call_kwargs = mock_create_chunk.call_args_list[0].kwargs
    # Fallback chunk must have all timestamp fields (not missing keys)
    assert "start_seconds" in call_kwargs
    assert "end_seconds" in call_kwargs
    assert "snippet" in call_kwargs
    assert call_kwargs["end_seconds"] == 40.0


# ---------------------------------------------------------------------------
# Regression: channel sync ?force=true replaces chunks on existing videos (#112)
# ---------------------------------------------------------------------------


async def test_channel_sync_force_replaces_chunks_on_existing_video():
    """force=true must refresh chunks on a video that already exists in the DB.

    The 20 videos in prod were ingested before PR #100 wired timestamped
    segments through the sync pipeline — they have start_seconds=0.0 and
    empty snippets. Without a force flag, sync_channel skips existing videos,
    so there is no way to backfill them. This test locks in the backfill
    path: existing video → replace_chunks_for_video with real timestamps,
    create_chunk not called, create_video not called.
    """
    from httpx import ASGITransport, AsyncClient

    fake_helper = AsyncMock(
        return_value={
            "youtube_video_id": "existing1",
            "title": "Existing Video",
            "description": "desc",
            "transcript": "Intro. Main. Outro.",
            "segments": [
                {"start": 0.0, "end": 30.0, "text": "Intro."},
                {"start": 30.0, "end": 90.0, "text": "Main."},
            ],
        }
    )

    chunk_dicts = [
        {"content": "Intro.", "start_seconds": 0.0, "end_seconds": 30.0, "snippet": "Intro."},
        {"content": "Main.", "start_seconds": 30.0, "end_seconds": 90.0, "snippet": "Main."},
    ]

    existing_video = {
        "id": "existing-video-uuid",
        "title": "Existing Video (stale)",
        "description": "stale",
        "url": "https://www.youtube.com/watch?v=existing1",
        "transcript": "stale transcript",
    }

    class MockChannelVideosResult:
        def __init__(self, ids: list[str]):
            self.video_ids = ids
            self.short_ids: list[str] = []
            self.live_ids: list[str] = []

    with (
        patch("backend.routes.channels.fetch_video_for_ingest", new=fake_helper),
        patch(
            "backend.routes.channels.chunk_video_timestamped",
            return_value=(chunk_dicts, False),
        ),
        patch(
            "backend.routes.channels.embed_batch",
            return_value=[[0.1] * 3, [0.2] * 3],
        ),
        patch(
            "backend.routes.channels.repo.get_video_by_youtube_id",
            new_callable=AsyncMock,
            return_value=existing_video,
        ),
        patch(
            "backend.routes.channels.repo.create_sync_run",
            new_callable=AsyncMock,
            return_value={"id": "run-1"},
        ),
        patch(
            "backend.routes.channels.repo.create_sync_video",
            new_callable=AsyncMock,
            return_value={"id": "sv-1"},
        ),
        patch(
            "backend.routes.channels.repo.update_sync_video_status",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.channels.repo.update_sync_run",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.channels.repo.create_video",
            new_callable=AsyncMock,
        ) as mock_create_video,
        patch(
            "backend.routes.channels.repo.create_chunk",
            new_callable=AsyncMock,
        ) as mock_create_chunk,
        patch(
            "backend.routes.channels.repo.replace_chunks_for_video",
            new_callable=AsyncMock,
        ) as mock_replace_chunks,
        patch("backend.services.supadata._get_client") as mock_get_client,
        patch("backend.rag.retriever.invalidate_cache"),
    ):
        mock_client = AsyncMock()
        mock_client.youtube.channel.videos = lambda *args, **kwargs: MockChannelVideosResult(
            ["existing1"]
        )
        mock_get_client.return_value = mock_client

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/channels/sync?force=true")

    assert response.status_code == 200
    data = response.json()
    assert data["videos_total"] == 1
    assert data["videos_new"] == 1
    assert data["videos_error"] == 0

    # The re-sync path must NOT create a new video row — reusing the existing one.
    mock_create_video.assert_not_called()
    # And must NOT go through the per-chunk insert path.
    mock_create_chunk.assert_not_called()
    # It MUST atomically replace chunks on the existing video id.
    mock_replace_chunks.assert_awaited_once()
    call = mock_replace_chunks.await_args
    assert call.args[0] == "existing-video-uuid"
    replaced = call.args[1]
    assert len(replaced) == 2
    # Real timestamps — the whole point of the backfill.
    assert replaced[0]["start_seconds"] == 0.0
    assert replaced[0]["end_seconds"] == 30.0
    assert replaced[0]["snippet"] == "Intro."
    assert replaced[1]["start_seconds"] == 30.0
    assert replaced[1]["end_seconds"] == 90.0
    assert replaced[1]["snippet"] == "Main."
    # chunk_index is required by replace_chunks_for_video.
    assert replaced[0]["chunk_index"] == 0
    assert replaced[1]["chunk_index"] == 1


async def test_channel_sync_without_force_still_skips_existing_video():
    """Default (force=false) must preserve the idempotent skip behaviour.

    The scheduled sync relies on this: re-running the sync must not re-ingest
    every previously-seen video. Only an explicit force=true triggers replace.
    """
    from httpx import ASGITransport, AsyncClient

    existing_video = {
        "id": "existing-video-uuid",
        "title": "Already in DB",
        "description": "desc",
        "url": "https://www.youtube.com/watch?v=existing1",
        "transcript": "old",
    }

    class MockChannelVideosResult:
        def __init__(self, ids: list[str]):
            self.video_ids = ids
            self.short_ids: list[str] = []
            self.live_ids: list[str] = []

    with (
        patch(
            "backend.routes.channels.repo.get_video_by_youtube_id",
            new_callable=AsyncMock,
            return_value=existing_video,
        ),
        patch(
            "backend.routes.channels.repo.create_sync_run",
            new_callable=AsyncMock,
            return_value={"id": "run-1"},
        ),
        patch(
            "backend.routes.channels.repo.create_sync_video",
            new_callable=AsyncMock,
            return_value={"id": "sv-1"},
        ),
        patch(
            "backend.routes.channels.repo.update_sync_video_status",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.channels.repo.update_sync_run",
            new_callable=AsyncMock,
        ),
        patch(
            "backend.routes.channels.fetch_video_for_ingest", new_callable=AsyncMock
        ) as mock_fetch,
        patch(
            "backend.routes.channels.repo.replace_chunks_for_video",
            new_callable=AsyncMock,
        ) as mock_replace_chunks,
        patch("backend.services.supadata._get_client") as mock_get_client,
        patch("backend.rag.retriever.invalidate_cache"),
    ):
        mock_client = AsyncMock()
        mock_client.youtube.channel.videos = lambda *args, **kwargs: MockChannelVideosResult(
            ["existing1"]
        )
        mock_get_client.return_value = mock_client

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # No force param — defaults to false.
            response = await ac.post("/api/channels/sync")

    assert response.status_code == 200
    # Existing video is skipped — no fetch, no replace.
    mock_fetch.assert_not_called()
    mock_replace_chunks.assert_not_called()
