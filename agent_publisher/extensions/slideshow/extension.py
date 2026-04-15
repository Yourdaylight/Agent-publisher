"""Slideshow extension — generate chapter-parallel HTML presentations from articles.

v3: No Playwright, no ffmpeg, no TTS dependencies.
Outputs independent chapter HTML files + browser player.
"""

from __future__ import annotations

from agent_publisher.extensions._base import Extension


class SlideshowExtension(Extension):
    name = "slideshow"
    label = "演示文稿"
    description = "从文章内容自动生成章节化 HTML 演示文稿，支持在线预览和离线浏览"
    version = "0.3.0"

    article_actions = [
        {
            "key": "slideshow_generate",
            "label": "生成演示文稿",
            "icon": "play-circle",
            "endpoint": "/api/extensions/slideshow/generate",
        },
    ]

    def check_dependencies(self) -> tuple[bool, str]:
        """No heavy dependencies required in v3."""
        try:
            import jinja2  # noqa: F401
        except ImportError:
            return False, "Missing jinja2 (install with: uv pip install jinja2)"

        return True, ""

    def register_routes(self, app) -> None:  # noqa: ANN001
        from agent_publisher.extensions.slideshow.routes import router

        app.include_router(router)


extension = SlideshowExtension()
