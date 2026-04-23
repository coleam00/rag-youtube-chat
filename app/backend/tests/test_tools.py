"""Tests for backend.rag.tools — four retrieval tools and their executors."""

from __future__ import annotations

import json

import pytest

from backend.llm.openrouter import build_system_prompt
from backend.rag import tools as tools_module
from backend.rag.tools import (
    GET_VIDEO_TRANSCRIPT_TOOL,
    KEYWORD_SEARCH_TOOL,
    SEARCH_VIDEOS_TOOL,
    SEMANTIC_SEARCH_TOOL,
    TOOL_SCHEMAS,
    _format_search_results,
    _format_transcript,
    execute_get_video_transcript,
    execute_search_hybrid,
    execute_search_keyword,
    execute_search_semantic,
    execute_tool,
    serialize_tool_result,
)

# --- Tool schemas ----------------------------------------------------------


@pytest.mark.parametrize(
    "schema,name",
    [
        (SEARCH_VIDEOS_TOOL, "search_videos"),
        (KEYWORD_SEARCH_TOOL, "keyword_search_videos"),
        (SEMANTIC_SEARCH_TOOL, "semantic_search_videos"),
        (GET_VIDEO_TRANSCRIPT_TOOL, "get_video_transcript"),
    ],
)
def test_tool_schemas_are_openai_function_format(schema, name) -> None:
    assert schema["type"] == "function"
    assert schema["function"]["name"] == name
    assert "description" in schema["function"]
    assert "parameters" in schema["function"]
    assert schema in TOOL_SCHEMAS


# --- Argument validation (shared across search tools) ---------------------


@pytest.mark.parametrize(
    "executor",
    [execute_search_hybrid, execute_search_keyword, execute_search_semantic],
)
@pytest.mark.asyncio
async def test_search_tools_require_non_empty_query(executor) -> None:
    assert (await executor({}))["ok"] is False
    assert (await executor({"query": "   "}))["ok"] is False
    assert (await executor("{not valid json"))["ok"] is False


@pytest.mark.asyncio
async def test_unknown_tool_name_returns_error() -> None:
    result = await execute_tool("not_a_real_tool", {})
    assert result["ok"] is False
    assert "unknown tool" in result["error"].lower()


# --- Search executors (happy paths, dependencies mocked) -------------------


_FAKE_CHUNKS = [
    {
        "chunk_id": "c1",
        "content": "First chunk text.",
        "video_id": "v1",
        "video_title": "How RAG Works",
        "video_url": "https://youtu.be/abc",
        "start_seconds": 0.0,
        "end_seconds": 30.0,
        "snippet": "First",
    },
]


@pytest.mark.asyncio
async def test_execute_search_hybrid_happy_path(monkeypatch) -> None:
    async def fake_retrieve(_q, _emb, top_k=5):
        assert top_k == 10
        return _FAKE_CHUNKS

    monkeypatch.setattr("backend.rag.retriever_hybrid.retrieve_hybrid", fake_retrieve)
    monkeypatch.setattr("backend.rag.embeddings.embed_text", lambda _s: [0.0] * 1536)

    result = await execute_search_hybrid(json.dumps({"query": "rag pipelines"}))
    assert result["ok"] is True
    assert "How RAG Works" in result["text"]
    assert "at 00:00" in result["text"]
    assert result["chunks"] == _FAKE_CHUNKS


@pytest.mark.asyncio
async def test_execute_search_keyword_hydrates_raw_chunks(monkeypatch) -> None:
    async def fake_keyword(_q, top_k=10, language="english"):
        return [
            {
                "id": "c1",
                "video_id": "v1",
                "content": "hello",
                "chunk_index": 0,
                "start_seconds": 0.0,
                "end_seconds": 1.0,
                "snippet": "hello",
            }
        ]

    async def fake_get_video(_v):
        return {"id": "v1", "title": "Kw Video", "url": "https://youtu.be/k"}

    monkeypatch.setattr(tools_module.repository, "keyword_search", fake_keyword)
    monkeypatch.setattr(tools_module.repository, "get_video", fake_get_video)

    result = await execute_search_keyword({"query": "hello"})
    assert result["ok"] is True
    assert "Kw Video" in result["text"]
    assert result["chunks"][0]["chunk_id"] == "c1"
    assert result["chunks"][0]["video_title"] == "Kw Video"


@pytest.mark.asyncio
async def test_execute_search_semantic_embeds_and_hydrates(monkeypatch) -> None:
    async def fake_vector(_emb, top_k=10):
        return [
            {
                "id": "c2",
                "video_id": "v2",
                "content": "semantic hit",
                "chunk_index": 0,
                "start_seconds": 42.0,
                "end_seconds": 60.0,
                "snippet": "semantic",
            }
        ]

    async def fake_get_video(_v):
        return {"id": "v2", "title": "Sem Video", "url": "https://youtu.be/s"}

    monkeypatch.setattr(tools_module.repository, "vector_search_pg", fake_vector)
    monkeypatch.setattr(tools_module.repository, "get_video", fake_get_video)
    monkeypatch.setattr("backend.rag.embeddings.embed_text", lambda _s: [0.0] * 1536)

    result = await execute_search_semantic({"query": "some concept"})
    assert result["ok"] is True
    assert "Sem Video" in result["text"]
    assert "at 00:42" in result["text"]
    assert result["chunks"][0]["chunk_id"] == "c2"


@pytest.mark.asyncio
async def test_search_empty_results_returns_canned_message(monkeypatch) -> None:
    async def fake_keyword(_q, top_k=10, language="english"):
        return []

    monkeypatch.setattr(tools_module.repository, "keyword_search", fake_keyword)

    result = await execute_search_keyword({"query": "nothing matches"})
    assert result["ok"] is True
    assert "No relevant chunks found" in result["text"]
    assert result["chunks"] == []


# --- Transcript tool -------------------------------------------------------


@pytest.mark.asyncio
async def test_transcript_missing_or_empty_video_id() -> None:
    assert (await execute_get_video_transcript({}))["ok"] is False
    assert (await execute_get_video_transcript({"video_id": "   "}))["ok"] is False
    assert (await execute_get_video_transcript({"video_id": 123}))["ok"] is False


@pytest.mark.asyncio
async def test_transcript_whitelist_rejects_unknown_id() -> None:
    result = await execute_get_video_transcript(
        {"video_id": "hallucinated"}, video_id_whitelist={"real-1"}
    )
    assert result["ok"] is False
    assert "library" in result["error"].lower()


@pytest.mark.asyncio
async def test_transcript_happy_path_returns_text_and_chunks(monkeypatch) -> None:
    async def fake_get_video(_v):
        return {"id": "v1", "title": "How RAG Works", "url": "https://youtu.be/abc"}

    async def fake_list(_v):
        return [
            {
                "id": "c1",
                "content": "First.",
                "chunk_index": 0,
                "start_seconds": 0.0,
                "end_seconds": 30.0,
                "snippet": "First",
            },
            {
                "id": "c2",
                "content": "Second.",
                "chunk_index": 1,
                "start_seconds": 30.0,
                "end_seconds": 65.0,
                "snippet": "Second",
            },
        ]

    monkeypatch.setattr(tools_module.repository, "get_video", fake_get_video)
    monkeypatch.setattr(tools_module.repository, "list_chunks_for_video", fake_list)

    result = await execute_tool(
        "get_video_transcript",
        json.dumps({"video_id": "v1"}),
        video_id_whitelist={"v1"},
    )
    assert result["ok"] is True
    assert "How RAG Works" in result["text"]
    assert "[00:00]" in result["text"]
    assert "[00:30]" in result["text"]
    assert len(result["chunks"]) == 2
    assert result["chunks"][0]["chunk_id"] == "c1"
    assert result["chunks"][0]["video_title"] == "How RAG Works"


# --- Formatting / serialization -------------------------------------------


def test_search_results_formatter_renders_timestamps_and_title() -> None:
    text = _format_search_results(_FAKE_CHUNKS)
    assert "How RAG Works" in text
    assert "at 00:00" in text


def test_transcript_formatter_handles_60_minute_edge() -> None:
    text = _format_transcript(
        {"title": "Demo"},
        [{"start_seconds": 3600.0, "content": "x"}],
    )
    assert "[60:00]" in text


def test_serialize_ok_returns_text() -> None:
    assert serialize_tool_result({"ok": True, "text": "hello"}) == "hello"


def test_serialize_error_returns_error_line() -> None:
    payload = serialize_tool_result({"ok": False, "error": "boom"})
    assert payload.startswith("Error:") and "boom" in payload


def test_serialize_malformed_returns_generic_error() -> None:
    assert serialize_tool_result({}).startswith("Error:")


# --- System prompt tool guidance ------------------------------------------


def test_prompt_includes_all_tools_when_cap_positive() -> None:
    prompt = build_system_prompt(max_tool_calls=6)
    for name in (
        "search_videos",
        "keyword_search_videos",
        "semantic_search_videos",
        "get_video_transcript",
    ):
        assert name in prompt


def test_prompt_omits_tool_guidance_when_cap_zero() -> None:
    prompt = build_system_prompt(max_tool_calls=0)
    assert "search_videos" not in prompt
