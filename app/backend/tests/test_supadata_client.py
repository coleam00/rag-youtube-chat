"""
Unit tests for the Supadata client (backend.services.supadata).

Tests the get_channel_video_ids and get_transcript functions using mocked
boundaries — httpx level is mocked via mock on the SDK client.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from supadata import SupadataError

from backend.services import supadata


# ---------------------------------------------------------------------------
# Mock client helpers
# ---------------------------------------------------------------------------


class MockChannelVideosResult:
    """Mimics the result shape of client.youtube.channel.videos()."""

    def __init__(self, video_ids=None, short_ids=None, live_ids=None):
        self.video_ids = video_ids or []
        self.short_ids = short_ids or []
        self.live_ids = live_ids or []


class MockTranscriptResult:
    """Mimics the result shape of client.youtube.transcript()."""

    def __init__(self, text="Sample transcript text."):
        self.text = text


# ---------------------------------------------------------------------------
# Tests: get_transcript
# ---------------------------------------------------------------------------


def _make_supadata_error(error, message, details, status):
    """Create a SupadataError with a status attribute like the real SDK does."""
    exc = SupadataError(error=error, message=message, details=details)
    exc.status = status
    return exc


@pytest.mark.asyncio
async def test_get_transcript_404_returns_none():
    """Transcript unavailable (404) returns None, not an exception."""

    def mock_transcript(video_id, lang):
        raise _make_supadata_error("not_found", "Transcript not found", "", 404)

    mock_client = AsyncMock()
    mock_client.youtube.transcript = mock_transcript

    with patch.object(supadata, "_get_client", return_value=mock_client):
        result = await supadata.get_transcript("abc123xyz")

    assert result is None


@pytest.mark.asyncio
async def test_get_transcript_400_returns_none():
    """Transcript unavailable (400) returns None, not an exception."""

    def mock_transcript(video_id, lang):
        raise _make_supadata_error("bad_request", "Bad request", "", 400)

    mock_client = AsyncMock()
    mock_client.youtube.transcript = mock_transcript

    with patch.object(supadata, "_get_client", return_value=mock_client):
        result = await supadata.get_transcript("abc123xyz")

    assert result is None


@pytest.mark.asyncio
async def test_get_transcript_429_retries_and_succeeds():
    """Transcript fetch 429 triggers one retry and succeeds on second attempt."""
    call_count = 0

    def mock_transcript(video_id, lang):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_supadata_error("rate_limited", "Rate limit exceeded", "", 429)
        return MockTranscriptResult(text="Success after retry")

    mock_client = AsyncMock()
    mock_client.youtube.transcript = mock_transcript

    with patch.object(supadata, "_get_client", return_value=mock_client):
        result = await supadata.get_transcript("abc123xyz")

    assert call_count == 2
    assert result == "Success after retry"


@pytest.mark.asyncio
async def test_get_transcript_429_exhausts_retries():
    """Transcript fetch 429 that always fails raises SupadataError after retries."""
    call_count = 0

    def mock_transcript(video_id, lang):
        nonlocal call_count
        call_count += 1
        raise _make_supadata_error("rate_limited", "Rate limit exceeded", "", 429)

    mock_client = AsyncMock()
    mock_client.youtube.transcript = mock_transcript

    with patch.object(supadata, "_get_client", return_value=mock_client):
        with pytest.raises(SupadataError) as exc_info:
            await supadata.get_transcript("abc123xyz")

    assert call_count == 3  # 3 attempts total
    assert exc_info.value.status == 429


@pytest.mark.asyncio
async def test_get_transcript_500_raises_supadata_error():
    """Transcript fetch 500 raises SupadataError (not generic Exception)."""

    def mock_transcript(video_id, lang):
        raise _make_supadata_error("server_error", "Internal server error", "", 500)

    mock_client = AsyncMock()
    mock_client.youtube.transcript = mock_transcript

    with patch.object(supadata, "_get_client", return_value=mock_client):
        with pytest.raises(SupadataError) as exc_info:
            await supadata.get_transcript("abc123xyz")

    assert exc_info.value.status == 500


@pytest.mark.asyncio
async def test_get_transcript_network_error_raises():
    """Network-level errors (TimeoutError, OSError) propagate as SupadataError."""
    # TimeoutError is not a SupadataError, so it gets wrapped
    def mock_transcript(video_id, lang):
        raise asyncio.TimeoutError("Request timed out")

    mock_client = AsyncMock()
    mock_client.youtube.transcript = mock_transcript

    with patch.object(supadata, "_get_client", return_value=mock_client):
        with pytest.raises(SupadataError):
            await supadata.get_transcript("abc123xyz")


@pytest.mark.asyncio
async def test_get_transcript_lang_parameter_passed():
    """get_transcript passes the lang='en' parameter to the SDK as required."""
    captured_args = {}

    def mock_transcript(video_id, lang):
        captured_args["video_id"] = video_id
        captured_args["lang"] = lang
        return MockTranscriptResult(text="English transcript.")

    mock_client = AsyncMock()
    mock_client.youtube.transcript = mock_transcript

    with patch.object(supadata, "_get_client", return_value=mock_client):
        await supadata.get_transcript("abc123xyz", lang="en")

    assert captured_args["video_id"] == "abc123xyz"
    assert captured_args["lang"] == "en"


# ---------------------------------------------------------------------------
# Tests: get_channel_video_ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_channel_video_ids_happy_path():
    """get_channel_video_ids returns video_ids, short_ids, live_ids correctly."""
    mock_result = MockChannelVideosResult(
        video_ids=["vid1", "vid2"],
        short_ids=["short1"],
        live_ids=["live1"],
    )

    mock_client = AsyncMock()
    mock_client.youtube.channel.videos = lambda *args, **kwargs: mock_result

    with patch.object(supadata, "_get_client", return_value=mock_client):
        result = await supadata.get_channel_video_ids("UC_testchannel", type="video")

    assert result["video_ids"] == ["vid1", "vid2"]
    assert result["short_ids"] == ["short1"]
    assert result["live_ids"] == ["live1"]


@pytest.mark.asyncio
async def test_get_channel_video_ids_429_retries_and_succeeds():
    """429 triggers one retry and succeeds on second attempt."""
    call_count = 0

    def mock_channel_videos(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_supadata_error("rate_limited", "Rate limit exceeded", "", 429)
        return MockChannelVideosResult(video_ids=["vid1"])

    mock_client = AsyncMock()
    mock_client.youtube.channel.videos = mock_channel_videos

    with patch.object(supadata, "_get_client", return_value=mock_client):
        result = await supadata.get_channel_video_ids("UC_testchannel")

    assert call_count == 2
    assert result["video_ids"] == ["vid1"]


@pytest.mark.asyncio
async def test_get_channel_video_ids_429_exhausts_retries():
    """429 that always fails raises SupadataError after 3 attempts."""
    call_count = 0

    def mock_channel_videos(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise _make_supadata_error("rate_limited", "Rate limit exceeded", "", 429)

    mock_client = AsyncMock()
    mock_client.youtube.channel.videos = mock_channel_videos

    with patch.object(supadata, "_get_client", return_value=mock_client):
        with pytest.raises(SupadataError) as exc_info:
            await supadata.get_channel_video_ids("UC_testchannel")

    assert call_count == 3
    assert exc_info.value.status == 429


@pytest.mark.asyncio
async def test_get_channel_video_ids_non_supadata_error_propagates():
    """Non-SupadataError exceptions propagate (not wrapped silently)."""

    def mock_channel_videos(*args, **kwargs):
        raise TypeError("SDK returned unexpected shape")

    mock_client = AsyncMock()
    mock_client.youtube.channel.videos = mock_channel_videos

    with patch.object(supadata, "_get_client", return_value=mock_client):
        # TypeError should propagate, not be caught and wrapped
        with pytest.raises(TypeError):
            await supadata.get_channel_video_ids("UC_testchannel")
