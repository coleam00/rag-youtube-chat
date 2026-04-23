"""
Message routes — POST /api/conversations/{conv_id}/messages

Orchestrates the tool-driven RAG flow:
  1. Verify conversation ownership (404 cross-user, no leak)
  2. Enforce 25 msg/user/24h cap
  3. Save user message
  4. Load conversation history
  5. Invoke the LLM with retrieval tools declared; the model drives
     retrieval via tool calls (search_videos, keyword_search_videos,
     semantic_search_videos, get_video_transcript). No pre-retrieval.
  6. Stream the response as SSE
  7. Send the sources event (populated from the model's tool calls) before [DONE]
  8. Persist the assistant message after the stream completes
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend import rate_limit
from backend.auth.dependencies import get_current_user
from backend.config import LLM_TOOLS_ENABLED, LLM_TOOLS_MAX_PER_TURN
from backend.db import repository
from backend.llm.openrouter import stream_chat
from backend.rag.tools import TOOL_SCHEMAS, execute_tool, serialize_tool_result

logger = logging.getLogger(__name__)

router = APIRouter()


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Message content (non-empty)")

    @field_validator("content", mode="before")
    @classmethod
    def content_not_whitespace_only(cls, v: str) -> str:
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("content must not be empty or whitespace-only")
        return v


# ---------------------------------------------------------------------------
# POST /api/conversations/{conv_id}/messages
# ---------------------------------------------------------------------------


@router.post("/conversations/{conv_id}/messages")
async def create_message(
    conv_id: str,
    body: MessageCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Send a user message and stream the RAG-grounded assistant response.

    Returns:
        StreamingResponse with Content-Type: text/event-stream
        Each SSE event: "data: <token>\n\n"
        Final event: "data: [DONE]\n\n"
    """
    user_id = str(current_user["id"])

    # 1. Verify conversation exists AND belongs to current user.
    # 404 (not 403) — don't leak existence of other users' conversations.
    conv = await repository.get_conversation(conv_id, user_id=user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 2. Enforce the 25 msg / user / 24h cap (MISSION §10 invariant #1).
    #    Must run BEFORE any LLM or DB write so a rate-limited user cannot
    #    consume OpenRouter budget or leave an orphan user-message row. The
    #    audit row is inserted inside `check_and_record` on pass — partial
    #    streams still count, users can't game the counter by aborting.
    try:
        await rate_limit.check_and_record(user_id)
    except rate_limit.RateLimitExceeded as exc:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "limit": rate_limit.DAILY_MESSAGE_CAP,
                "window_hours": rate_limit.WINDOW_HOURS,
                "reset_at": exc.reset_at.isoformat(),
            },
        )

    # Content is already validated non-empty by Pydantic; strip for storage
    user_content = body.content.strip()

    # 3. Persist the user message. create_message re-checks ownership atomically
    # so a race between the check above and insert can't leak cross-user.
    inserted = await repository.create_message(
        conversation_id=conv_id,
        user_id=user_id,
        role="user",
        content=user_content,
    )
    if inserted is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 4. Retrieve conversation history for LLM context
    all_messages = await repository.list_messages(conv_id, user_id=user_id)
    llm_messages = [{"role": m["role"], "content": m["content"]} for m in all_messages]

    # 5. Set up tool plumbing. All retrieval happens inside the LLM loop via
    # tool calls — no pre-retrieval runs here. The executor closure collects
    # every chunk returned by any tool call so the final SSE `sources` event
    # lists exactly what the model actually read. The video_id whitelist is
    # only consulted by the transcript tool (it guards against hallucinated
    # ids); the search tools ignore it.
    source_citations: list[dict] = []
    tool_chunks_acc: list[dict] = []
    tools_param: list[dict] | None = None
    executor = None
    max_tool_calls = 0
    if LLM_TOOLS_ENABLED:
        try:
            all_videos = await repository.list_videos()
            video_id_whitelist: set[str] = {v["id"] for v in all_videos if v.get("id")}
        except Exception as exc:
            logger.warning(
                "Failed to load video whitelist for tool use; transcript tool calls will be unguarded: %s",
                exc,
            )
            video_id_whitelist = set()

        async def _executor(name: str, raw_args: str) -> str:
            # Pass `None` (not empty set) when the whitelist failed to load so
            # the transcript tool falls back to open lookups instead of rejecting
            # every id.
            whitelist = video_id_whitelist if video_id_whitelist else None
            result = await execute_tool(name, raw_args, video_id_whitelist=whitelist)
            if result.get("ok") and result.get("chunks"):
                tool_chunks_acc.extend(result["chunks"])
            return serialize_tool_result(result)

        tools_param = TOOL_SCHEMAS
        executor = _executor
        max_tool_calls = LLM_TOOLS_MAX_PER_TURN

    # 6. Stream the response. The model drives retrieval via tool calls;
    # chunks it pulls flow into source_citations via tool_chunks_acc.
    async def event_generator() -> AsyncGenerator[str, None]:
        full_response = []
        try:
            async for sse_chunk in stream_chat(
                llm_messages,
                tools=tools_param,
                tool_executor=executor,
                max_tool_calls=max_tool_calls,
            ):
                # Intercept [DONE] to inject the sources event first.
                if sse_chunk == "data: [DONE]\n\n":
                    if tool_chunks_acc:
                        seen: set[str] = set()
                        for tc in tool_chunks_acc:
                            tc_id = tc.get("chunk_id")
                            if tc_id and tc_id not in seen:
                                source_citations.append(tc)
                                seen.add(tc_id)
                    if source_citations:
                        sources_json = json.dumps(source_citations)
                        yield f"event: sources\ndata: {sources_json}\n\n"
                full_response.append(sse_chunk)
                yield sse_chunk
        finally:
            # 7. Persist the complete assistant message
            assistant_text = _extract_text_from_sse(full_response)
            if assistant_text:
                try:
                    await repository.create_message(
                        conversation_id=conv_id,
                        user_id=user_id,
                        role="assistant",
                        content=assistant_text,
                        sources=source_citations if source_citations else None,
                    )
                    # Auto-generate title on first assistant reply
                    await _maybe_set_conversation_title(conv_id, user_id, user_content)
                except Exception as exc:
                    logger.error("Failed to persist assistant message: %s", exc)
                    raise  # Re-raise to surface the error to FastAPI

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text_from_sse(sse_chunks: list[str]) -> str:
    """
    Reconstruct the full assistant text from a list of SSE event strings.
    Each chunk looks like "data: <json-encoded-token>\n\n".
    Tokens are JSON-encoded strings to safely handle newlines and special characters.
    """
    tokens = []
    for chunk in sse_chunks:
        if not chunk.startswith("data: "):
            continue
        content = chunk[len("data: ") :].rstrip("\n")
        if not content or content == "[DONE]":
            continue
        # Skip JSON error payloads
        if content.startswith('{"error"'):
            continue
        # Try to decode JSON-encoded token (new format)
        try:
            decoded = json.loads(content)
            if isinstance(decoded, str):
                tokens.append(decoded)
            # If it's something else (shouldn't happen), skip it
        except ValueError:
            # Fallback: treat as raw text (backward compat with unencoded tokens)
            tokens.append(content)
    return "".join(tokens)


async def _maybe_set_conversation_title(
    conv_id: str, user_id: str, first_user_message: str
) -> None:
    """
    If the conversation title is still the default, auto-generate one from
    the first user message (simple truncation for Sprint 2; LLM-based in Sprint 6).
    """
    conv = await repository.get_conversation(conv_id, user_id=user_id)
    if not conv:
        return
    if conv.get("title") == "New Conversation":
        if len(first_user_message) > 50:
            title = first_user_message[:47].strip() + "…"
        else:
            title = first_user_message.strip()
        await repository.update_conversation_title(conv_id, user_id=user_id, title=title)
