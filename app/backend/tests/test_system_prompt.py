"""Regression tests for the RAG system prompt.

Pin two behaviors the factory rules care about:
  1. The prompt forbids raw ids in the assistant's prose (issue #93).
  2. The prompt no longer injects pre-retrieved context — retrieval is
     entirely tool-driven now — and it tells the model to use its tools.
"""

from __future__ import annotations

from backend.llm.openrouter import SYSTEM_PROMPT_TEMPLATE, build_system_prompt


class TestSystemPromptForbidsRawIds:
    def test_template_forbids_raw_ids(self) -> None:
        assert "video IDs" in SYSTEM_PROMPT_TEMPLATE or "video id" in SYSTEM_PROMPT_TEMPLATE.lower()
        assert "title only" in SYSTEM_PROMPT_TEMPLATE.lower()

    def test_built_prompt_contains_rule(self) -> None:
        prompt = build_system_prompt(max_tool_calls=6).lower()
        assert "never write youtube video ids" in prompt
        assert "title only" in prompt


class TestSystemPromptToolBased:
    def test_prompt_has_no_context_placeholder(self) -> None:
        # Retrieval is tool-driven; no pre-retrieved context is injected.
        prompt = build_system_prompt(max_tool_calls=0)
        assert "{context}" not in prompt
        assert "Context:" not in prompt

    def test_prompt_mentions_all_tools_when_enabled(self) -> None:
        prompt = build_system_prompt(max_tool_calls=6)
        for tool_name in (
            "search_videos",
            "keyword_search_videos",
            "semantic_search_videos",
            "get_video_transcript",
        ):
            assert tool_name in prompt
        assert "6 tool calls" in prompt or "6 " in prompt  # cap echoed in guidance

    def test_prompt_omits_tool_guidance_when_cap_zero(self) -> None:
        prompt = build_system_prompt(max_tool_calls=0)
        assert "search_videos" not in prompt
