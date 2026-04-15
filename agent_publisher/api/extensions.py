"""Extensions metadata API — lists all loaded extensions."""

from __future__ import annotations

from fastapi import APIRouter

from agent_publisher.extensions import registry

router = APIRouter(prefix="/api/extensions", tags=["extensions"])


@router.get("")
async def list_extensions():
    """Return metadata for all loaded extensions (name, label, article_actions, …)."""
    return {"extensions": registry.list_metadata()}
