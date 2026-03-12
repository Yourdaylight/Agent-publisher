"""Media asset library API: upload, list, download, delete image assets."""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.config import settings
from agent_publisher.models.media import MediaAsset

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])

# Upload directory: data/uploads/ relative to project root
UPLOAD_DIR = Path(os.environ.get("MEDIA_UPLOAD_DIR", "data/uploads"))

# Allowed image MIME types
ALLOWED_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
    "image/svg+xml", "image/bmp", "image/tiff",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _ensure_upload_dir():
    """Ensure the upload directory exists."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _get_media_with_ownership(
    media_id: int, user: UserContext, db: AsyncSession
) -> MediaAsset:
    """Fetch a media asset and verify ownership."""
    asset = await db.get(MediaAsset, media_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    if not user.is_admin and asset.owner_email != user.email:
        raise HTTPException(status_code=403, detail="Access denied")
    return asset


@router.post("")
async def upload_media(
    file: UploadFile = File(...),
    tags: str = Query("", description="Comma-separated tags"),
    description: str = Query("", description="Asset description"),
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Upload an image/media file to the asset library."""
    _ensure_upload_dir()

    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large ({file_size} bytes). Max: {MAX_FILE_SIZE}")
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Generate stored filename with UUID
    original_filename = file.filename or "unnamed"
    ext = Path(original_filename).suffix or ".png"
    stored_filename = f"{uuid.uuid4().hex}{ext}"

    # Write to disk
    file_path = UPLOAD_DIR / stored_filename
    file_path.write_bytes(content)

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Save to database
    asset = MediaAsset(
        filename=original_filename,
        stored_filename=stored_filename,
        content_type=content_type,
        file_size=file_size,
        tags=tag_list,
        description=description,
        owner_email=user.email,  # Set owner to current user
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    logger.info("Media uploaded: id=%d filename=%s size=%d", asset.id, original_filename, file_size)
    return {
        "id": asset.id,
        "filename": asset.filename,
        "stored_filename": asset.stored_filename,
        "content_type": asset.content_type,
        "file_size": asset.file_size,
        "tags": asset.tags,
        "description": asset.description,
        "url": f"/api/media/{asset.id}/download",
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.get("")
async def list_media(
    tag: str = Query("", description="Filter by tag"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List media assets, optionally filtered by tag."""
    stmt = select(MediaAsset).order_by(MediaAsset.id.desc())
    if not user.is_admin:
        stmt = stmt.where(MediaAsset.owner_email == user.email)

    if tag:
        # JSON contains for SQLite/Postgres
        stmt = stmt.where(MediaAsset.tags.contains(tag))

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    assets = result.scalars().all()

    return [
        {
            "id": a.id,
            "filename": a.filename,
            "content_type": a.content_type,
            "file_size": a.file_size,
            "tags": a.tags or [],
            "description": a.description,
            "owner_email": a.owner_email,
            "url": f"/api/media/{a.id}/download",
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in assets
    ]


@router.get("/{media_id}")
async def get_media_detail(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get media asset detail by ID."""
    asset = await _get_media_with_ownership(media_id, user, db)
    return {
        "id": asset.id,
        "filename": asset.filename,
        "stored_filename": asset.stored_filename,
        "content_type": asset.content_type,
        "file_size": asset.file_size,
        "tags": asset.tags or [],
        "description": asset.description,
        "owner_email": asset.owner_email,
        "url": f"/api/media/{asset.id}/download",
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.get("/{media_id}/download")
async def download_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Download (serve) the media file."""
    from fastapi.responses import FileResponse

    asset = await db.get(MediaAsset, media_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    file_path = UPLOAD_DIR / asset.stored_filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        media_type=asset.content_type,
        filename=asset.filename,
    )


@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Delete a media asset."""
    asset = await _get_media_with_ownership(media_id, user, db)

    # Remove file from disk
    file_path = UPLOAD_DIR / asset.stored_filename
    if file_path.is_file():
        file_path.unlink()

    await db.delete(asset)
    await db.commit()
    logger.info("Media deleted: id=%d filename=%s", media_id, asset.filename)
    return {"ok": True, "deleted_id": media_id}


@router.put("/{media_id}")
async def update_media(
    media_id: int,
    tags: str = Query("", description="Comma-separated tags (replaces existing)"),
    description: str = Query("", description="New description"),
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Update media asset metadata (tags, description)."""
    asset = await _get_media_with_ownership(media_id, user, db)

    if tags:
        asset.tags = [t.strip() for t in tags.split(",") if t.strip()]
    if description:
        asset.description = description

    await db.commit()
    await db.refresh(asset)
    return {
        "id": asset.id,
        "filename": asset.filename,
        "tags": asset.tags or [],
        "description": asset.description,
    }
