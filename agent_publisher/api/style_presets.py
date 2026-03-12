"""Admin API for style preset management."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.services.style_preset_service import StylePresetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/style-presets", tags=["style-presets"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class StylePresetCreate(BaseModel):
    style_id: str
    name: str
    description: str = ""
    prompt: str = ""


class StylePresetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt: str | None = None


class StylePresetOut(BaseModel):
    id: int
    style_id: str
    name: str
    description: str
    prompt: str
    is_builtin: bool
    created_at: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[StylePresetOut])
async def list_style_presets(db: AsyncSession = Depends(get_db)):
    """List all style presets (built-in + custom)."""
    svc = StylePresetService(db)
    presets = await svc.list_presets()
    return [
        StylePresetOut(
            id=p.id,
            style_id=p.style_id,
            name=p.name,
            description=p.description,
            prompt=p.prompt,
            is_builtin=p.is_builtin,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in presets
    ]


@router.post("", response_model=StylePresetOut)
async def create_style_preset(
    data: StylePresetCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a custom style preset."""
    svc = StylePresetService(db)
    try:
        preset = await svc.create_preset(
            style_id=data.style_id,
            name=data.name,
            description=data.description,
            prompt=data.prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return StylePresetOut(
        id=preset.id,
        style_id=preset.style_id,
        name=preset.name,
        description=preset.description,
        prompt=preset.prompt,
        is_builtin=preset.is_builtin,
        created_at=preset.created_at.isoformat() if preset.created_at else None,
    )


@router.put("/{style_id}", response_model=StylePresetOut)
async def update_style_preset(
    style_id: str,
    data: StylePresetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Edit a style preset (builtin and custom are both editable)."""
    svc = StylePresetService(db)
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        preset = await svc.update_preset(style_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return StylePresetOut(
        id=preset.id,
        style_id=preset.style_id,
        name=preset.name,
        description=preset.description,
        prompt=preset.prompt,
        is_builtin=preset.is_builtin,
        created_at=preset.created_at.isoformat() if preset.created_at else None,
    )


@router.delete("/{style_id}")
async def delete_style_preset(
    style_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom style preset. Built-in presets return 403."""
    svc = StylePresetService(db)
    try:
        await svc.delete_preset(style_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"ok": True, "deleted": style_id}
