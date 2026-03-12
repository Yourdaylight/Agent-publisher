"""Candidate Materials API: browse, filter, tag, and manually upload materials."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.schemas.candidate_material import (
    CandidateMaterialCreate,
    CandidateMaterialListParams,
    CandidateMaterialOut,
    CandidateMaterialTagUpdate,
)
from agent_publisher.services.candidate_material_service import CandidateMaterialService

router = APIRouter(prefix="/api/candidate-materials", tags=["materials"])


# ---------------------------------------------------------------------------
# Manual upload
# ---------------------------------------------------------------------------

class ManualUploadRequest(BaseModel):
    title: str
    content: str = ""
    original_url: str = ""
    tags: list[str] = []


@router.post("/upload", response_model=CandidateMaterialOut)
async def upload_material(
    data: ManualUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually upload a candidate material. Automatically tagged as 'manual'."""
    svc = CandidateMaterialService(db)
    create_data = CandidateMaterialCreate(
        source_type="manual",
        source_identity="manual_upload",
        original_url=data.original_url,
        title=data.title,
        summary=data.content[:500] if data.content else "",
        raw_content=data.content,
        tags=data.tags,
        agent_id=None,
    )
    material = await svc.ingest(create_data)
    return material


# ---------------------------------------------------------------------------
# List / filter
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
async def list_materials(
    agent_id: int | None = Query(None),
    source_type: str | None = Query(None),
    status: str | None = Query(None),
    tags: str | None = Query(None, description="Comma-separated tag list"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List candidate materials with filtering and pagination."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    params = CandidateMaterialListParams(
        agent_id=agent_id,
        source_type=source_type,
        status=status,
        tags=tag_list,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    svc = CandidateMaterialService(db)
    items, total = await svc.list_materials(params)
    return {
        "items": [CandidateMaterialOut.model_validate(m) for m in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@router.get("/{material_id}", response_model=CandidateMaterialOut)
async def get_material(
    material_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single candidate material with full details."""
    svc = CandidateMaterialService(db)
    material = await svc.get_by_id(material_id)
    if not material:
        raise HTTPException(404, "Material not found")
    return material


# ---------------------------------------------------------------------------
# Tag management
# ---------------------------------------------------------------------------

@router.patch("/{material_id}/tags", response_model=CandidateMaterialOut)
async def update_material_tags(
    material_id: int,
    data: CandidateMaterialTagUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Add or remove tags on a candidate material."""
    svc = CandidateMaterialService(db)
    material = await svc.update_tags(material_id, data)
    if not material:
        raise HTTPException(404, "Material not found")
    return material
