"""WeChatStyleService — deterministic inline style injection for WeChat OA.

Applies WeChat-compatible inline styles to HTML content so articles display
correctly in WeChat Official Account (which does NOT support <style> tags).

All styling is done via inline `style` attributes on individual tags.
Tags that already have a `style` attribute are left untouched to preserve
user-customized formatting.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# Style definitions (matching ai_beautify_html WeChat conventions)
# ---------------------------------------------------------------------------

_PARAGRAPH_STYLE = (
    "font-size: 16px; line-height: 1.75; color: #3f3f3f; "
    "margin-bottom: 20px; letter-spacing: 0.5px;"
)

_HEADING_STYLES: dict[str, str] = {
    "h1": "font-size: 24px; font-weight: bold; color: #1a1a1a; margin: 30px 0 15px; text-align: center;",
    "h2": "font-size: 22px; font-weight: bold; color: #1a1a1a; margin: 25px 0 12px; border-bottom: 2px solid #07C160; padding-bottom: 8px;",
    "h3": "font-size: 20px; font-weight: bold; color: #1a1a1a; margin: 20px 0 10px;",
    "h4": "font-size: 18px; font-weight: bold; color: #1a1a1a; margin: 18px 0 8px;",
    "h5": "font-size: 17px; font-weight: bold; color: #3f3f3f; margin: 15px 0 8px;",
    "h6": "font-size: 16px; font-weight: bold; color: #3f3f3f; margin: 15px 0 8px;",
}

_LINK_STYLE = "color: #07C160; text-decoration: none; border-bottom: 1px solid #07C160;"

_BLOCKQUOTE_STYLE = (
    "border-left: 4px solid #07C160; background: #f8f8f8; "
    "padding: 12px 16px; margin: 16px 0; color: #666; font-size: 15px; "
    "border-radius: 0 4px 4px 0;"
)

_INLINE_CODE_STYLE = (
    "font-family: 'Menlo', 'Monaco', 'Consolas', monospace; "
    "background: #f0f0f0; padding: 2px 6px; border-radius: 3px; "
    "font-size: 14px; color: #c7254e;"
)

_CODE_BLOCK_STYLE = (
    "font-family: 'Menlo', 'Monaco', 'Consolas', monospace; "
    "background: #f6f8fa; padding: 16px; border-radius: 4px; "
    "font-size: 14px; line-height: 1.6; overflow-x: auto; "
    "margin: 16px 0; white-space: pre-wrap; word-wrap: break-word;"
)

_IMAGE_STYLE = "max-width: 100%; border-radius: 4px; display: block; margin: 16px auto;"

_LIST_STYLE = "margin: 10px 0; padding-left: 24px;"

_LIST_ITEM_STYLE = "margin-bottom: 8px; line-height: 1.75; color: #3f3f3f;"

_HR_STYLE = "border: none; border-top: 1px solid #e0e0e0; margin: 24px 0;"

_STRONG_STYLE = "font-weight: bold; color: #1a1a1a;"

_EM_STYLE = "font-style: italic; color: #3f3f3f;"


# Tag → default style mapping (full set, used for unstyled HTML)
_TAG_STYLES: dict[str, str] = {
    "p": _PARAGRAPH_STYLE,
    **_HEADING_STYLES,
    "a": _LINK_STYLE,
    "blockquote": _BLOCKQUOTE_STYLE,
    "code": _INLINE_CODE_STYLE,
    "pre": _CODE_BLOCK_STYLE,
    "img": _IMAGE_STYLE,
    "ul": _LIST_STYLE,
    "ol": _LIST_STYLE,
    "li": _LIST_ITEM_STYLE,
    "hr": _HR_STYLE,
    "strong": _STRONG_STYLE,
    "em": _EM_STYLE,
}

# Tags that wenyan does NOT style — lightweight supplement for wenyan output
_SUPPLEMENT_TAG_STYLES: dict[str, str] = {
    "strong": _STRONG_STYLE,
    "em": _EM_STYLE,
}


class _StyleInjector(HTMLParser):
    """HTML parser that injects inline styles into tags."""

    def __init__(self) -> None:
        super().__init__()
        self._output: list[str] = []
        self._tag_stack: list[str] = []

    def reset(self) -> None:
        super().reset()
        self._output = []
        self._tag_stack = []

    def get_output(self) -> str:
        return "".join(self._output)

    # -- helpers --

    @staticmethod
    def _build_open_tag(tag: str, attrs: list[tuple[str, str | None]], self_closing: bool) -> str:
        parts = [tag]
        for name, value in attrs:
            if value is None:
                parts.append(name)
            else:
                parts.append(f'{name}="{value}"')
        closing = " /" if self_closing else ""
        return "<" + " ".join(parts) + closing + ">"

    def _has_style_attr(self, attrs: list[tuple[str, str | None]]) -> bool:
        return any(name == "style" and value for name, value in attrs)

    # -- parser callbacks --

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        style_def = _TAG_STYLES.get(tag)

        if style_def and not self._has_style_attr(attrs):
            # Inject style attribute
            attrs_with_style = list(attrs) + [("style", style_def)]
            self._output.append(self._build_open_tag(tag, attrs_with_style, self_closing=False))
        else:
            self._output.append(self._build_open_tag(tag, attrs, self_closing=False))

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        self._output.append(f"</{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        style_def = _TAG_STYLES.get(tag)
        if style_def and not self._has_style_attr(attrs):
            attrs_with_style = list(attrs) + [("style", style_def)]
            self._output.append(self._build_open_tag(tag, attrs_with_style, self_closing=True))
        else:
            self._output.append(self._build_open_tag(tag, attrs, self_closing=True))

    def handle_data(self, data: str) -> None:
        self._output.append(data)

    def handle_entityref(self, name: str) -> None:
        self._output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self._output.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._output.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self._output.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self._output.append(f"<![{data}]>")


class _SupplementInjector(_StyleInjector):
    """Injects styles only for the supplement tag set (strong, em).

    Used on wenyan output where most tags already have inline styles.
    """

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        style_def = _SUPPLEMENT_TAG_STYLES.get(tag)

        if style_def and not self._has_style_attr(attrs):
            attrs_with_style = list(attrs) + [("style", style_def)]
            self._output.append(self._build_open_tag(tag, attrs_with_style, self_closing=False))
        else:
            self._output.append(self._build_open_tag(tag, attrs, self_closing=False))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        style_def = _SUPPLEMENT_TAG_STYLES.get(tag)
        if style_def and not self._has_style_attr(attrs):
            attrs_with_style = list(attrs) + [("style", style_def)]
            self._output.append(self._build_open_tag(tag, attrs_with_style, self_closing=True))
        else:
            self._output.append(self._build_open_tag(tag, attrs, self_closing=True))


class WeChatStyleService:
    """Deterministic inline-style injection for WeChat Official Account HTML.

    Usage::

        styled_html = WeChatStyleService.inject_styles(raw_html)
        # For wenyan output (already has most styles):
        styled_html = WeChatStyleService.inject_styles_supplement(wenyan_html)
    """

    @staticmethod
    def inject_styles(html: str) -> str:
        """Inject WeChat-compatible inline styles into HTML.

        Tags that already have a ``style`` attribute are left untouched,
        preserving any user-customized formatting.

        Args:
            html: Raw HTML string (may contain unstyled tags).

        Returns:
            HTML string with inline styles applied to supported tags.
        """
        if not html or not html.strip():
            return html

        # Quick check: if there are no HTML tags at all, return as-is
        if not re.search(r"<[a-zA-Z]", html):
            return html

        injector = _StyleInjector()
        injector.feed(html)
        return injector.get_output()

    @staticmethod
    def inject_styles_supplement(html: str) -> str:
        """Lightweight style injection for tags wenyan misses (strong, em).

        Use this on wenyan output where most tags already have inline styles.
        Only injects styles for ``<strong>`` and ``<em>`` — tags that wenyan
        does not style. Tags with existing ``style`` attributes are preserved.

        Args:
            html: Wenyan-rendered HTML string.

        Returns:
            HTML string with supplementary styles applied.
        """
        if not html or not html.strip():
            return html

        if not re.search(r"<[a-zA-Z]", html):
            return html

        injector = _SupplementInjector()
        injector.feed(html)
        return injector.get_output()
