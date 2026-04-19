"""YouTube metadata via the public oEmbed endpoint.

Supadata's `youtube.video()` SDK method can't be parsed by the current
Pydantic model (YoutubeVideo rejects the `is_live` field the API returns),
so we pull the bits we actually need — title and author — from YouTube's
own oEmbed endpoint. No auth, no key, safe for 20-5000 calls per sync.
"""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_OEMBED_URL = "https://www.youtube.com/oembed"
_YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"


async def _fetch_og_description(video_id: str) -> str | None:
    """Scrape og:description from the YouTube video page as a fallback.

    YouTube embeds the video description in:
        <meta property="og:description" content="DESCRIPTION TEXT">

    Returns None on any failure (network error, non-200, missing tag).
    """
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            },
        ) as client:
            resp = await client.get(watch_url)
            if resp.status_code != 200:
                return None
            html = resp.text
            match = re.search(
                r'<meta\s+(?:property|name)=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
                html,
            )
            if not match:
                return None
            content = match.group(1)
            return content or None
    except Exception as exc:
        logger.warning("og:description scrape failed for %s: %s", video_id, exc)
        return None


async def _make_request(url: str, params: dict[str, str]) -> httpx.Response | None:
    """Make an HTTP GET request, returning None on any failure."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            return resp if resp.status_code == 200 else None
    except Exception as exc:
        logger.warning("HTTP request failed for %s: %s", url, exc)
        return None


async def get_video_title(video_id: str) -> str | None:
    """Return the YouTube video title, or None if the lookup fails."""
    params = {
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "format": "json",
    }
    resp = await _make_request(_OEMBED_URL, params)
    if resp is None:
        return None
    return resp.json().get("title") or None


async def get_video_description(video_id: str) -> str | None:
    """Return the YouTube video description, or None if the lookup fails."""
    from backend.config import YOUTUBE_API_KEY

    if not YOUTUBE_API_KEY:
        return await _fetch_og_description(video_id)

    params = {
        "part": "snippet",
        "id": video_id,
        "key": YOUTUBE_API_KEY,
        "hl": "en",
    }
    resp = await _make_request(_YOUTUBE_API_URL, params)
    if resp is None:
        return None
    items = resp.json().get("items", [])
    description = items[0].get("snippet", {}).get("description", "") if items else ""
    return description or None
