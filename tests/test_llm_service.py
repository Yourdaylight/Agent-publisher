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
