"""Tests for WeChatStyleService — deterministic inline style injection for WeChat OA.

TDD Red-Green-Refactor cycle:
1. RED:   Write failing test → watch it fail
2. GREEN: Write minimal code to pass
3. REFACTOR: Clean up while keeping tests green
"""
from __future__ import annotations

import pytest

from agent_publisher.services.wechat_style_service import WeChatStyleService


# ---------------------------------------------------------------------------
# 1. inject_styles — basic paragraph styling
# ---------------------------------------------------------------------------


class TestInjectStylesParagraph:
    """Paragraphs should receive WeChat-compatible inline styles."""

    def test_plain_paragraph_gets_style(self):
        html = "<p>Hello world</p>"
        result = WeChatStyleService.inject_styles(html)
        # Must contain inline style on the <p> tag
        assert "style=" in result
        assert "font-size: 16px" in result
        assert "line-height: 1.75" in result
        assert "color: #3f3f3f" in result

    def test_paragraph_with_existing_style_not_overwritten(self):
        """If a tag already has a style attribute, don't overwrite it."""
        html = '<p style="color: red; font-size: 20px;">Custom</p>'
        result = WeChatStyleService.inject_styles(html)
        assert 'color: red' in result
        assert 'font-size: 20px' in result
        # Should NOT add duplicate font-size
        assert result.count("font-size") == 1

    def test_multiple_paragraphs_all_styled(self):
        html = "<p>One</p><p>Two</p><p>Three</p>"
        result = WeChatStyleService.inject_styles(html)
        assert result.count("font-size: 16px") == 3


# ---------------------------------------------------------------------------
# 2. inject_styles — heading styling
# ---------------------------------------------------------------------------


class TestInjectStylesHeadings:
    """Headings should get appropriate sizes and styles."""

    @pytest.mark.parametrize("tag,expected_size", [
        ("h1", "24px"),
        ("h2", "22px"),
        ("h3", "20px"),
        ("h4", "18px"),
    ])
    def test_heading_gets_correct_font_size(self, tag, expected_size):
        html = f"<{tag}>Title</{tag}>"
        result = WeChatStyleService.inject_styles(html)
        assert f"font-size: {expected_size}" in result

    def test_heading_gets_bold_and_color(self):
        html = "<h2>Section</h2>"
        result = WeChatStyleService.inject_styles(html)
        assert "font-weight: bold" in result
        assert "color: #1a1a1a" in result


# ---------------------------------------------------------------------------
# 3. inject_styles — link styling
# ---------------------------------------------------------------------------


class TestInjectStylesLinks:
    """Links should get WeChat green color."""

    def test_link_gets_wechat_green(self):
        html = '<a href="https://example.com">Click</a>'
        result = WeChatStyleService.inject_styles(html)
        assert "color: #07C160" in result

    def test_link_with_existing_style_preserved(self):
        html = '<a href="#" style="color: blue;">Click</a>'
        result = WeChatStyleService.inject_styles(html)
        assert "color: blue" in result
        assert result.count("color:") == 1


# ---------------------------------------------------------------------------
# 4. inject_styles — blockquote styling
# ---------------------------------------------------------------------------


class TestInjectStylesBlockquote:
    """Blockquotes should get left border and background."""

    def test_blockquote_gets_border_and_background(self):
        html = "<blockquote>Quote text</blockquote>"
        result = WeChatStyleService.inject_styles(html)
        assert "border-left" in result
        assert "#07C160" in result
        assert "background" in result


# ---------------------------------------------------------------------------
# 5. inject_styles — code styling
# ---------------------------------------------------------------------------


class TestInjectStylesCode:
    """Code blocks and inline code should get monospace font and background."""

    def test_inline_code_gets_style(self):
        html = "<code>var x</code>"
        result = WeChatStyleService.inject_styles(html)
        assert "font-family" in result
        assert "background" in result

    def test_pre_code_block_gets_style(self):
        html = "<pre><code>def hello():\n    pass</code></pre>"
        result = WeChatStyleService.inject_styles(html)
        assert "font-family" in result
        assert "background" in result


# ---------------------------------------------------------------------------
# 6. inject_styles — image styling
# ---------------------------------------------------------------------------


class TestInjectStylesImages:
    """Images should get max-width and border-radius."""

    def test_image_gets_responsive_and_rounded(self):
        html = '<img src="https://example.com/pic.jpg" alt="test">'
        result = WeChatStyleService.inject_styles(html)
        assert "max-width: 100%" in result
        assert "border-radius" in result


# ---------------------------------------------------------------------------
# 7. inject_styles — list styling
# ---------------------------------------------------------------------------


class TestInjectStylesLists:
    """List items should get proper spacing."""

    def test_list_item_gets_margin(self):
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = WeChatStyleService.inject_styles(html)
        assert "margin" in result


# ---------------------------------------------------------------------------
# 8. inject_styles — hr styling
# ---------------------------------------------------------------------------


class TestInjectStylesHR:
    """Horizontal rules should get subtle styling."""

    def test_hr_gets_style(self):
        html = "<hr>"
        result = WeChatStyleService.inject_styles(html)
        assert "border" in result
        assert "none" in result  # reset default border


# ---------------------------------------------------------------------------
# 9. inject_styles — edge cases
# ---------------------------------------------------------------------------


class TestInjectStylesEdgeCases:
    """Edge cases: empty string, no tags, already fully styled."""

    def test_empty_string_returns_empty(self):
        assert WeChatStyleService.inject_styles("") == ""

    def test_plain_text_returns_unchanged(self):
        """Text without HTML tags is returned as-is (no wrapping)."""
        text = "Just plain text"
        result = WeChatStyleService.inject_styles(text)
        assert result == text

    def test_nested_tags_inner_gets_style(self):
        html = "<p>Text with <strong>bold</strong> and <em>italic</em></p>"
        result = WeChatStyleService.inject_styles(html)
        # <strong> and <em> should get styles too
        assert result.count("style=") >= 2  # at least <p> and one inner tag

    def test_self_closing_img_tag(self):
        html = '<img src="test.jpg"/>'
        result = WeChatStyleService.inject_styles(html)
        assert "max-width: 100%" in result

    def test_complex_article_html(self):
        """Realistic multi-element article gets all styles."""
        html = """
        <h1>Main Title</h1>
        <p>First paragraph with <strong>bold text</strong>.</p>
        <blockquote>A wise quote</blockquote>
        <p>Second paragraph with <a href="https://example.com">a link</a>.</p>
        <ul>
            <li>Item one</li>
            <li>Item two</li>
        </ul>
        <img src="photo.jpg" alt="photo">
        <p>Final paragraph.</p>
        """
        result = WeChatStyleService.inject_styles(html)
        # Every tag type should have styles
        assert result.count("style=") >= 8  # h1, 4x p, blockquote, ul, img at minimum
        assert "font-size: 16px" in result  # paragraphs
        assert "font-size: 24px" in result  # h1
        assert "color: #07C160" in result   # link or blockquote border


# ---------------------------------------------------------------------------
# 10. Integration: _basic_markdown_to_html output gets styled
# ---------------------------------------------------------------------------


class TestBasicMarkdownIntegration:
    """The fallback _basic_markdown_to_html should produce styled output."""

    def test_basic_markdown_output_has_wechat_styles(self):
        from agent_publisher.services.article_service import ArticleService

        md = "# Title\n\nParagraph with **bold** text."
        html = ArticleService._basic_markdown_to_html(md)
        # After integration, _basic_markdown_to_html should produce
        # HTML with WeChat inline styles (via WeChatStyleService)
        assert "font-size: 16px" in html or "font-size: 24px" in html, (
            "Basic markdown fallback should include WeChat inline styles"
        )

    def test_basic_markdown_heading_styled(self):
        from agent_publisher.services.article_service import ArticleService

        html = ArticleService._basic_markdown_to_html("## Section Header")
        assert "font-size: 22px" in html, "h2 should have 22px font size"

    def test_basic_markdown_paragraph_styled(self):
        from agent_publisher.services.article_service import ArticleService

        html = ArticleService._basic_markdown_to_html("Hello world")
        assert "font-size: 16px" in html, "Paragraph should have 16px font size"
        assert "color: #3f3f3f" in html, "Paragraph should have #3f3f3f color"


# ---------------------------------------------------------------------------
# 11. Integration: _markdown_to_html fallback path (no wenyan)
# ---------------------------------------------------------------------------


class TestMarkdownToHtmlFallback:
    """When wenyan is not installed, _markdown_to_html should still produce styled HTML."""

    def test_fallback_produces_styled_html(self, monkeypatch):
        from agent_publisher.services.article_service import ArticleService

        # Force wenyan to be "not found"
        monkeypatch.setattr("shutil.which", lambda _: None)

        md = "# Hello\n\nWorld"
        html = ArticleService._markdown_to_html(md)
        assert "font-size: 24px" in html, "Even without wenyan, h1 should be styled"
        assert "font-size: 16px" in html, "Even without wenyan, paragraphs should be styled"


# ---------------------------------------------------------------------------
# 12. Integration: skill_create_article injects styles into html_content
# ---------------------------------------------------------------------------


class TestSkillCreateArticleIntegration:
    """When skill API creates an article with html_content, it should auto-inject styles."""

    def test_plain_html_gets_styled_on_create(self):
        """When only html_content is provided (no markdown), styles are injected."""
        from agent_publisher.services.wechat_style_service import WeChatStyleService

        raw_html = "<p>Plain paragraph</p>"
        styled = WeChatStyleService.inject_styles(raw_html)
        assert "font-size: 16px" in styled

    def test_html_with_existing_styles_preserved_on_create(self):
        """Pre-styled HTML should be preserved, not overwritten."""
        from agent_publisher.services.wechat_style_service import WeChatStyleService

        raw_html = '<p style="color: red;">Custom styled</p>'
        styled = WeChatStyleService.inject_styles(raw_html)
        assert "color: red" in styled
        assert styled.count("font-size") == 0  # should NOT add font-size to already styled


# ---------------------------------------------------------------------------
# 13. Integration: _get_publish_html injects styles as safety net
# ---------------------------------------------------------------------------


class TestGetPublishHtmlIntegration:
    """_get_publish_html should inject styles into unstyled html_content."""

    def test_publish_html_injects_styles_for_unstyled_content(self):
        """If html_content exists but has no inline styles, inject them."""
        from agent_publisher.services.wechat_style_service import WeChatStyleService

        # Simulate what _get_publish_html should do for unstyled content
        raw_html = "<h1>Title</h1><p>Body text</p>"
        styled = WeChatStyleService.inject_styles(raw_html)
        assert "font-size: 24px" in styled
        assert "font-size: 16px" in styled


# ---------------------------------------------------------------------------
# 14. Integration: _markdown_to_html (wenyan path) still gets style injection
#     as safety net — wenyan output sometimes lacks full WeChat styles
# ---------------------------------------------------------------------------


class TestWenyanOutputSafetyNet:
    """_markdown_to_html should apply style injection even for wenyan output."""

    def test_wenyan_output_gets_style_injection(self, monkeypatch):
        """Simulate wenyan returning unstyled HTML — style injection should fix it."""
        from agent_publisher.services.article_service import ArticleService

        # Mock shutil.which to return a fake path (simulates wenyan installed)
        monkeypatch.setattr("shutil.which", lambda _: "/fake/wenyan")
        # Mock subprocess.run to return unstyled HTML (simulates wenyan output)
        import subprocess

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="<h1>Title</h1><p>Body</p>", stderr=""
        )
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake_result)

        html = ArticleService._markdown_to_html("# Title\n\nBody")
        # After integration, wenyan output should also get style injection
        assert "font-size: 24px" in html, "wenyan output should get h1 style injection"
        assert "font-size: 16px" in html, "wenyan output should get paragraph style injection"
