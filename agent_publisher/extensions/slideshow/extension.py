"""Slideshow extension — generate reveal.js presentations from articles."""
from __future__ import annotations

from agent_publisher.extensions._base import Extension


class SlideshowExtension(Extension):
    name = "slideshow"
    label = "演示文稿"
    description = "从文章内容自动生成 reveal.js 演示文稿，支持在线预览和视频导出"
    version = "0.1.0"

    article_actions = [
        {
            "key": "slideshow_generate",
            "label": "生成演示文稿",
            "icon": "play-circle",
            "endpoint": "/api/extensions/slideshow/generate",
        },
    ]

    def check_dependencies(self) -> tuple[bool, str]:
        """Check that playwright is importable."""
        try:
            import playwright  # noqa: F401
        except ImportError:
            return False, "Missing playwright (install with: uv pip install -e '.[slideshow]')"

        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False, "Missing edge-tts (install with: uv pip install -e '.[tts]')"

        return True, ""

    def register_routes(self, app) -> None:  # noqa: ANN001
        # Lazy import to avoid pulling in heavy deps at startup
        from agent_publisher.extensions.slideshow.routes import router

        app.include_router(router)


extension = SlideshowExtension()
