"""MiniMax image generation service — wraps the ``mmx`` CLI tool.

Uses MiniMax's image-01 model via the ``mmx image generate`` command.
The CLI handles authentication via ``~/.mmx/config.json`` (set up with
``mmx auth login``).

Generated images are saved locally, then uploaded as MediaAsset entries
so they can be served via the /api/media endpoint and used in articles.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class MiniMaxImageService:
    """Generate images using MiniMax CLI (mmx image generate)."""

    def __init__(self, region: str = "cn"):
        self.region = region
        self._mmx_bin = shutil.which("mmx")
        if not self._mmx_bin:
            logger.warning("mmx CLI not found — MiniMax image generation disabled")

    @property
    def available(self) -> bool:
        return self._mmx_bin is not None

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
    ) -> str:
        """Generate an image and return the local file path.

        Args:
            prompt: Image description text.
            aspect_ratio: e.g. "16:9", "1:1", "9:16".

        Returns:
            Absolute path to the generated image file.

        Raises:
            RuntimeError: If mmx is not installed or generation fails.
        """
        if not self._mmx_bin:
            raise RuntimeError("mmx CLI not installed. Run: npm install -g mmx-cli")

        out_dir = tempfile.mkdtemp(prefix="mmx-img-")
        result = await asyncio.to_thread(self._run_generate, prompt, aspect_ratio, out_dir)
        return result

    def _run_generate(self, prompt: str, aspect_ratio: str, out_dir: str) -> str:
        """Synchronous wrapper that calls mmx CLI."""
        import subprocess

        cmd = [
            self._mmx_bin,
            "image",
            "generate",
            "--prompt",
            prompt,
            "--aspect-ratio",
            aspect_ratio,
            "--out-dir",
            out_dir,
            "--output",
            "json",
            "--region",
            self.region,
        ]

        logger.info("MiniMax image generate: aspect=%s prompt=%.60s...", aspect_ratio, prompt)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("MiniMax image generation timed out (120s)")

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"mmx image generate failed: {error_msg}")

        # Parse JSON output — format: {"saved": ["/path/to/image_001.jpg"]}
        # mmx prefixes some lines like "[Model: image-01]" before JSON
        stdout = result.stdout.strip()
        json_start = stdout.find("{")
        if json_start == -1:
            raise RuntimeError(f"mmx output not JSON: {stdout[:200]}")

        try:
            data = json.loads(stdout[json_start:])
        except json.JSONDecodeError:
            raise RuntimeError(f"mmx output parse error: {stdout[:200]}")

        saved = data.get("saved", [])
        if not saved:
            raise RuntimeError("mmx returned no images")

        image_path = saved[0]
        if not os.path.exists(image_path):
            raise RuntimeError(f"Generated image not found: {image_path}")

        logger.info("MiniMax image generated: %s", image_path)
        return image_path

    async def generate_and_upload(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        description: str = "",
        db_session=None,
    ) -> dict:
        """Generate image and upload as MediaAsset.

        Returns:
            {"url": str, "media_id": int, "file_path": str}
        """
        image_path = await self.generate_image(prompt, aspect_ratio)

        try:
            # Read file content
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Determine content type
            ext = Path(image_path).suffix.lower()
            content_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }.get(ext, "image/jpeg")

            # If db_session provided, create MediaAsset
            if db_session:
                from agent_publisher.models.media import MediaAsset

                stored_name = f"mmx-{uuid.uuid4().hex[:12]}{ext}"
                # Store in data/uploads (same dir as media API)
                upload_dir = Path(os.environ.get("MEDIA_UPLOAD_DIR", "data/uploads"))
                upload_dir.mkdir(parents=True, exist_ok=True)
                dest_path = upload_dir / stored_name
                shutil.copy2(image_path, dest_path)

                media = MediaAsset(
                    filename=f"minimax-image{ext}",
                    stored_filename=stored_name,
                    content_type=content_type,
                    file_size=len(image_data),
                    source_kind="article_cover" if "封面" in description else "article_body",
                    description=description or prompt[:100],
                    tags=["ai-generated", "minimax"],
                )
                db_session.add(media)
                await db_session.flush()

                url = f"/api/media/{media.id}/download"
                logger.info("MiniMax image uploaded: media_id=%d stored=%s", media.id, stored_name)
                return {
                    "url": url,
                    "media_id": media.id,
                    "file_path": str(dest_path),
                }

            # No db session — return local file path
            return {
                "url": image_path,
                "media_id": None,
                "file_path": image_path,
            }
        finally:
            # Clean up temp dir
            temp_dir = str(Path(image_path).parent)
            if temp_dir.startswith(tempfile.gettempdir()):
                shutil.rmtree(temp_dir, ignore_errors=True)
