from __future__ import annotations

import pytest

from agent_publisher.services.llm_service import LLMService


def test_build_article_messages_default_template():
    """build_article_messages should produce system + user messages."""
    messages = LLMService.build_article_messages(
        topic="AI科技",
        news_list="- News 1\n- News 2",
        prompt_template="",
        agent_description="",
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "AI科技" in messages[0]["content"]
    assert "News 1" in messages[1]["content"]


def test_build_article_messages_custom_template():
    """Custom prompt template should be used when provided."""
    template = "Topic: {topic}\nNews:\n{news_list}\nStyle: {style}"
    messages = LLMService.build_article_messages(
        topic="Finance",
        news_list="- Stock up",
        prompt_template=template,
        agent_description="You are a finance editor.",
    )
    assert messages[0]["content"] == "You are a finance editor."
    assert "Finance" in messages[1]["content"]
    assert "Stock up" in messages[1]["content"]


def test_parse_article_response():
    """parse_article_response should extract title, digest, content."""
    text = "---TITLE---\nTest Title\n---DIGEST---\nTest Digest\n---CONTENT---\nSome **content**"
    result = LLMService.parse_article_response(text)
    assert result["title"] == "Test Title"
    assert result["digest"] == "Test Digest"
    assert "content" in result["content"]


def test_parse_article_response_no_markers():
    """Without markers, the whole text becomes content."""
    text = "Just a plain article without markers."
    result = LLMService.parse_article_response(text)
    assert result["content"] == text
    assert result["title"] == ""


@pytest.mark.asyncio
async def test_generate_invalid_provider():
    """Calling generate with unknown provider raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        await LLMService.generate("nonexistent", "model", "key", [])


# ── P0 Fix: Template without {news_list} must still include material content ──


class TestNewsListAlwaysIncluded:
    """CRITICAL: Verify that material content (news_list) ALWAYS reaches the LLM,
    regardless of prompt template configuration.

    This was a P0 bug: custom templates that didn't include {news_list} caused
    str.format() to silently discard all material content, making the LLM generate
    articles with no reference to the source materials.
    """

    def test_template_without_placeholder_includes_news(self):
        """Template without {news_list} must still include the news content."""
        msgs = LLMService.build_article_messages(
            topic="Finance",
            news_list="Stock market crashes 10%",
            prompt_template="Write a financial analysis article with expert insights",
            agent_description="",
        )
        assert "Stock market crashes 10%" in msgs[1]["content"], (
            "P0 BUG: Template without {news_list} silently dropped all material content"
        )

    def test_stray_braces_dont_crash(self):
        """Templates with literal braces (JSON, code snippets) don't crash."""
        msgs = LLMService.build_article_messages(
            topic="Dev",
            news_list="New API released",
            prompt_template='Use this format: {"key": "value"}',
            agent_description="",
        )
        assert "New API released" in msgs[1]["content"]

    def test_mode_instructions_preserve_news(self):
        """Mode instructions appended to prompt still include news_list."""
        # Simulate what article_service does: append mode text to prompt_text
        prompt = "Write a cool article\n\n创作模式：爆款二创。基于以下素材进行二次创作"
        msgs = LLMService.build_article_messages(
            topic="AI",
            news_list="Important material content",
            prompt_template=prompt,
            agent_description="",
        )
        assert "Important material content" in msgs[1]["content"]
        assert "爆款二创" in msgs[1]["content"]

    def test_output_format_always_present(self):
        """Output format markers (---TITLE---) present in all cases."""
        # No template
        msgs = LLMService.build_article_messages("AI", "news", "", "")
        assert "---TITLE---" in msgs[1]["content"]

        # With template (no markers)
        msgs = LLMService.build_article_messages("AI", "news", "Write about {news_list}", "")
        assert "---TITLE---" in msgs[1]["content"]

        # Template without placeholder
        msgs = LLMService.build_article_messages("AI", "news", "Write an article", "")
        assert "---TITLE---" in msgs[1]["content"]

    def test_output_format_not_duplicated(self):
        """Output format not duplicated if template already includes it."""
        template = (
            "Write about {news_list}\n---TITLE---\n标题\n---DIGEST---\n摘要\n---CONTENT---\n正文"
        )
        msgs = LLMService.build_article_messages("AI", "news", template, "")
        assert msgs[1]["content"].count("---TITLE---") == 1

    def test_agent_description_overrides_system_prompt(self):
        """When agent_description is provided, it replaces the default system prompt."""
        msgs = LLMService.build_article_messages(
            topic="AI", news_list="news", prompt_template="", agent_description="你是金融专家"
        )
        assert msgs[0]["content"] == "你是金融专家"

    def test_default_system_prompt_includes_topic(self):
        """Without agent_description, system prompt references the topic."""
        msgs = LLMService.build_article_messages(
            topic="量子计算", news_list="news", prompt_template="", agent_description=""
        )
        assert "量子计算" in msgs[0]["content"]
