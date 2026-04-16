"""数据源管理 REST API"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.models.agent import Agent
from agent_publisher.schemas.source_config import (
    AgentSourceBindingCreate,
    AgentSourceBindingOut,
    CollectResult,
    SourceConfigCreate,
    SourceConfigOut,
    SourceConfigUpdate,
    ToggleRequest,
    TRENDING_PLATFORMS,
)
from agent_publisher.services.rss_service import RSSService
from agent_publisher.services.source_registry_service import SourceRegistryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sources", tags=["sources"])


# ── SourceConfig CRUD ─────────────────────────────────────────────────


@router.post("", response_model=SourceConfigOut)
async def create_source(
    data: SourceConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """创建数据源"""
    svc = SourceRegistryService(db)
    # Check for duplicate source_key
    existing = await svc.get_source_by_key(data.source_key)
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Source key '{data.source_key}' already exists"
        )
    return await svc.create_source(data)


@router.get("", response_model=list[SourceConfigOut])
async def list_sources(
    source_type: str | None = None,
    is_enabled: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """列出数据源"""
    svc = SourceRegistryService(db)
    return await svc.list_sources(source_type=source_type, is_enabled=is_enabled)


@router.get("/trending-platforms")
async def get_trending_platforms(
    user: UserContext = Depends(get_current_user),
):
    """获取支持的热榜平台列表"""
    return TRENDING_PLATFORMS


@router.get("/{source_id}", response_model=SourceConfigOut)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """获取数据源详情"""
    svc = SourceRegistryService(db)
    source = await svc.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.put("/{source_id}", response_model=SourceConfigOut)
async def update_source(
    source_id: int,
    data: SourceConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """更新数据源"""
    svc = SourceRegistryService(db)
    source = await svc.update_source(source_id, data)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.delete("/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """删除数据源"""
    svc = SourceRegistryService(db)
    deleted = await svc.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"ok": True}


@router.patch("/{source_id}/toggle", response_model=SourceConfigOut)
async def toggle_source(
    source_id: int,
    body: ToggleRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """启用/禁用数据源"""
    svc = SourceRegistryService(db)
    source = await svc.toggle_source(source_id, body.is_enabled)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


# ── Agent 绑定管理 ────────────────────────────────────────────────────


@router.get("/agents/{agent_id}/bindings", response_model=list[AgentSourceBindingOut])
async def list_agent_bindings(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """获取 Agent 的数据源绑定列表"""
    svc = SourceRegistryService(db)
    return await svc.list_agent_bindings(agent_id)


@router.post("/agents/{agent_id}/bindings", response_model=AgentSourceBindingOut)
async def bind_agent_source(
    agent_id: int,
    data: AgentSourceBindingCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """绑定 Agent 到数据源"""
    # Verify agent exists
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    svc = SourceRegistryService(db)
    # Verify source exists
    source = await svc.get_source(data.source_config_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return await svc.bind_agent(agent_id, data)


@router.delete("/agents/{agent_id}/bindings/{source_id}")
async def unbind_agent_source(
    agent_id: int,
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """解绑 Agent 与数据源"""
    svc = SourceRegistryService(db)
    removed = await svc.unbind_agent(agent_id, source_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Binding not found")
    return {"ok": True}


# ── 采集操作 ──────────────────────────────────────────────────────────


@router.post("/agents/{agent_id}/collect")
async def collect_for_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """手动触发 Agent 采集"""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    svc = SourceRegistryService(db)
    result = await svc.collect_for_agent(agent)

    # Format response
    collect_results = []
    for source_type, ids in result.items():
        collect_results.append(
            CollectResult(
                source_type=source_type,
                material_ids=ids,
                count=len(ids),
            )
        )

    total = sum(r.count for r in collect_results)
    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "total_collected": total,
        "results": [r.model_dump() for r in collect_results],
    }


@router.post("/test-rss")
async def test_rss(
    body: dict,
    user: UserContext = Depends(get_current_user),
):
    """测试 RSS URL 可达性"""
    url = body.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    result = await RSSService.test_feed(url)
    return result
