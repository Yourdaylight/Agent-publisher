"""Video extension — generate short videos from articles using Remotion.

Uses Remotion (React-based video rendering) to produce MP4 videos.
LLM generates the scene script, Remotion renders the final video.
"""
from __future__ import annotations

from agent_publisher.extensions._base import Extension


class VideoExtension(Extension):
    name = "video"
    label = "短视频"
    description = "从文章内容自动生成竖屏短视频（Remotion 渲染），支持在线预览和下载 MP4"
    version = "1.0.0"

    article_actions = [
        {
            "key": "video_generate",
            "label": "生成短视频",
            "icon": "video",
            "endpoint": "/api/extensions/video/generate",
        },
    ]

    def check_dependencies(self) -> tuple[bool, str]:
        """Check that Node.js and Remotion are available."""
        import shutil
        import subprocess

        node = shutil.which("node")
        if not node:
            return False, "Missing Node.js (required for Remotion rendering)"

        try:
            result = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return False, "node --version failed"
        except Exception as exc:
            return False, f"Cannot run node: {exc}"

        return True, ""

    def register_routes(self, app) -> None:  # noqa: ANN001
        from agent_publisher.extensions.video.routes import router

        app.include_router(router)


extension = VideoExtension()
