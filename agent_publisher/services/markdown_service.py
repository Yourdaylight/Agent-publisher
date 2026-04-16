from __future__ import annotations

import logging
import mimetypes
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.media import MediaAsset

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class MarkdownService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def process_markdown(
        self,
        content: str,
        owner_email: str,
        tags: list[str] | None = None,
    ) -> tuple[str, list[dict]]:
        """Process markdown content, downloading remote images and uploading to media library.

        Returns:
            Tuple of (processed_markdown, image_infos)
            image_infos: list of {original_url, media_id, filename, url}
        """
        tags = tags or []

        # Extract markdown images
        img_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
        matches = list(img_pattern.finditer(content))

        image_infos: list[dict] = []
        replaced_content = content

        for match in matches:
            alt_text = match.group(1)
            original_url = match.group(2).strip()

            # Skip non-http(s) URLs
            if not original_url.startswith("http://") and not original_url.startswith("https://"):
                logger.debug("Skipping non-HTTP image: %s", original_url)
                continue

            # Skip if already a media library URL or wechat image
            if "/api/media/" in original_url or "weixin.qq.com" in original_url:
                logger.debug("Skipping already-local or wechat image: %s", original_url)
                continue

            try:
                # Download image
                image_bytes, filename, content_type = await self._download_image(original_url)

                # Upload to media library
                media_asset = await self._upload_to_media(
                    content=image_bytes,
                    filename=filename,
                    content_type=content_type,
                    owner_email=owner_email,
                    tags=tags + ["markdown_upload"],
                    source_url=original_url,
                )

                # Build replacement URL
                localized_url = f"/api/media/{media_asset.id}/download"
                original_markdown = match.group(0)
                new_markdown = f"![{alt_text}]({localized_url})"
                replaced_content = replaced_content.replace(original_markdown, new_markdown, 1)

                image_infos.append(
                    {
                        "original_url": original_url,
                        "media_id": media_asset.id,
                        "filename": filename,
                        "url": localized_url,
                    }
                )

                logger.info(
                    "Markdown image processed: url=%s -> media_id=%d",
                    original_url,
                    media_asset.id,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to process markdown image %s: %s",
                    original_url,
                    exc,
                )
                # Keep original URL on failure

        return replaced_content, image_infos

    async def _download_image(self, url: str) -> tuple[bytes, str, str]:
        """Download a remote image and return (bytes, filename, content_type)."""
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            img_resp = await client.get(url)
            img_resp.raise_for_status()
            parsed = urlparse(url)
            filename = parsed.path.rsplit("/", 1)[-1] or "image"
            content_type = img_resp.headers.get("content-type", "").split(";", 1)[0]
            guessed_content_type = content_type or mimetypes.guess_type(filename)[0] or "image/jpeg"
            # If filename has no extension, add one based on content type
            if not Path(filename).suffix:
                ext = mimetypes.guess_extension(guessed_content_type) or ".png"
                filename = f"{filename}{ext}"
            return img_resp.content, filename, guessed_content_type

    async def _upload_to_media(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        owner_email: str,
        tags: list[str],
        source_url: str,
    ) -> MediaAsset:
        """Upload bytes to media library and return the MediaAsset."""
        from agent_publisher.api.media import UPLOAD_DIR

        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"Image too large: {len(content)} bytes (max {MAX_FILE_SIZE})")

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix or mimetypes.guess_extension(content_type) or ".png"
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        (UPLOAD_DIR / stored_filename).write_bytes(content)

        media_asset = MediaAsset(
            filename=filename,
            stored_filename=stored_filename,
            content_type=content_type,
            file_size=len(content),
            tags=tags,
            description=f"Uploaded from markdown: {source_url}",
            owner_email=owner_email,
            source_kind="markdown_upload",
            source_url=source_url,
        )
        self.session.add(media_asset)
        await self.session.flush()
        return media_asset
