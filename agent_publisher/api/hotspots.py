from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import (
    UserContext,
    get_current_user,
    get_db,
    get_visible_emails,
    require_admin,
)
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.candidate_material import CandidateMaterial
from agent_publisher.services.article_service import ArticleService
from agent_publisher.services.source_registry_service import SourceRegistryService

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])


class HotspotCreateArticleRequest(BaseModel):
    agent_id: int | None = None
    prompt_template_id: int | None = None
    style_id: str | None = None
    user_prompt: str | None = None
    mode: str | None = None  # rewrite / summary / expand
    extra_material_ids: list[int] | None = (
        None  # additional hotspot IDs for multi-material creation
    )


class HotspotExportRequest(BaseModel):
    platform: str | None = None
    tag: str | None = None
    keyword: str | None = None
    limit: int = 200


def _serialize_hotspot(item: CandidateMaterial) -> dict:
    metadata = item.extra_metadata or {}
    return {
        "id": item.id,
        "title": item.title,
        "summary": item.summary,
        "original_url": item.original_url,
        "tags": item.tags or [],
        "quality_score": item.quality_score,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "metadata": metadata,
    }


def _extract_platform(item: CandidateMaterial) -> str:
    metadata = item.extra_metadata or {}
    platform = metadata.get("platform_name") or metadata.get("platform")
    if platform:
        return str(platform)
    for tag in item.tags or []:
        if isinstance(tag, str) and tag.startswith("platform:"):
            return tag.replace("platform:", "")
    return "未知"


async def _load_visible_hotspots(db: AsyncSession, user: UserContext) -> list[CandidateMaterial]:
    stmt = (
        select(CandidateMaterial)
        .where(
            CandidateMaterial.source_type == "trending",
            CandidateMaterial.is_duplicate.is_(False),
        )
        .order_by(CandidateMaterial.created_at.desc())
    )
    if not user.is_admin:
        visible_emails = await get_visible_emails(user, db)
        stmt = (
            stmt.join(Agent, CandidateMaterial.agent_id == Agent.id, isouter=True)
            .join(Account, Agent.account_id == Account.id, isouter=True)
            .where(
                (CandidateMaterial.agent_id.is_(None)) | (Account.owner_email.in_(visible_emails))
            )
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _matches_time_range(item: CandidateMaterial, time_range: str | None) -> bool:
    if not time_range or not item.created_at:
        return True

    now = datetime.now(timezone.utc)
    created_at = item.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    if time_range == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return created_at >= start
    if time_range == "3d":
        return created_at >= now - timedelta(days=3)
    if time_range == "7d":
        return created_at >= now - timedelta(days=7)
    return True


def _apply_hotspot_filters(
    items: list[CandidateMaterial],
    *,
    platform: str | None = None,
    platforms: list[str] | None = None,
    tag: str | None = None,
    keyword: str | None = None,
    heat_min: float | None = None,
    heat_max: float | None = None,
    time_range: str | None = None,
) -> list[CandidateMaterial]:
    filtered = items

    platform_filters = [value.strip().lower() for value in (platforms or []) if value.strip()]
    if platform and platform.strip():
        platform_filters.append(platform.strip().lower())
    if platform_filters:
        filtered = [
            item for item in filtered if _extract_platform(item).lower() in platform_filters
        ]

    if tag:
        filtered = [item for item in filtered if tag in (item.tags or [])]

    if keyword:
        keyword_lower = keyword.lower()
        filtered = [
            item
            for item in filtered
            if keyword_lower in (item.title or "").lower()
            or keyword_lower in (item.summary or "").lower()
        ]

    if heat_min is not None:
        filtered = [item for item in filtered if (item.quality_score or 0) >= heat_min]

    if heat_max is not None:
        filtered = [item for item in filtered if (item.quality_score or 0) <= heat_max]

    if time_range:
        filtered = [item for item in filtered if _matches_time_range(item, time_range)]

    return filtered


@router.get("")
async def list_hotspots(
    platform: str | None = None,
    platforms: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
    heat_min: float | None = None,
    heat_max: float | None = None,
    time_range: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    items = await _load_visible_hotspots(db, user)
    filtered = _apply_hotspot_filters(
        items,
        platform=platform,
        platforms=platforms.split(",") if platforms else None,
        tag=tag,
        keyword=keyword,
        heat_min=heat_min,
        heat_max=heat_max,
        time_range=time_range,
    )
    total = len(filtered)
    page_items = filtered[offset : offset + limit]
    return {
        "items": [_serialize_hotspot(item) for item in page_items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/platforms")
async def list_hotspot_platforms(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    items = await _load_visible_hotspots(db, user)
    counter = Counter(
        _extract_platform(item)
        for item in items
        if _extract_platform(item) and _extract_platform(item) != "未知"
    )
    return [{"value": name, "label": name, "count": count} for name, count in counter.most_common()]


@router.get("/{hotspot_id}")
async def get_hotspot(
    hotspot_id: int,
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(get_current_user),
):
    item = await db.get(CandidateMaterial, hotspot_id)
    if not item or item.source_type != "trending":
        raise HTTPException(status_code=404, detail="Hotspot not found")
    return _serialize_hotspot(item)


@router.get("/{hotspot_id}/trend")
async def get_hotspot_trend(
    hotspot_id: int,
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(get_current_user),
):
    item = await db.get(CandidateMaterial, hotspot_id)
    if not item or item.source_type != "trending":
        raise HTTPException(status_code=404, detail="Hotspot not found")
    metadata = item.extra_metadata or {}
    score = float(item.quality_score or 0)
    base = max(score, 0.1)
    return {
        "hotspot_id": hotspot_id,
        "points": [
            {"label": "24h前", "score": round(base * 0.42, 3)},
            {"label": "12h前", "score": round(base * 0.68, 3)},
            {"label": "6h前", "score": round(base * 0.84, 3)},
            {"label": "当前", "score": round(base, 3)},
        ],
        "platform": metadata.get("platform_name") or metadata.get("platform") or "未知",
    }


@router.post("/export")
async def export_hotspots(
    data: HotspotExportRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    payload = await list_hotspots(
        platform=data.platform,
        tag=data.tag,
        keyword=data.keyword,
        limit=data.limit,
        offset=0,
        db=db,
        user=user,
    )
    items = payload["items"]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "标题", "摘要", "链接", "标签", "质量分", "创建时间"])
    for item in items:
        writer.writerow(
            [
                item["id"],
                item["title"],
                item["summary"],
                item["original_url"],
                ", ".join(item["tags"]),
                item["quality_score"],
                item["created_at"],
            ]
        )
    output = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="hotspots.csv"'},
    )


@router.post("/refresh")
async def refresh_hotspots(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    require_admin(user)
    svc = SourceRegistryService(db)
    result = await svc.collect_all_trending()
    return {
        "ok": True,
        **result,
    }


@router.post("/{hotspot_id}/create-article")
async def create_article_from_hotspot(
    hotspot_id: int,
    data: HotspotCreateArticleRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    hotspot = await db.get(CandidateMaterial, hotspot_id)
    if not hotspot or hotspot.source_type != "trending":
        raise HTTPException(status_code=404, detail="Hotspot not found")

    agent: Agent | None = None
    if data.agent_id:
        agent = await db.get(Agent, data.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if not user.is_admin:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != user.email:
                raise HTTPException(status_code=403, detail="Access denied")
    else:
        # No agent specified — try the built-in agent first, fallback to transient
        builtin_result = await db.execute(select(Agent).where(Agent.is_builtin.is_(True)).limit(1))
        agent = builtin_result.scalar_one_or_none()
        if agent is None:
            # Build a rich transient agent with vertical context from the hotspot
            platform = (hotspot.extra_metadata or {}).get("platform_name", "")
            agent = Agent(
                id=None,
                name="默认写作身份",
                topic=hotspot.title[:40],
                description=(
                    f"你是一个专注于热点话题的公众号内容编辑。"
                    f"当前话题「{hotspot.title}」"
                    f"{'来自' + platform if platform else ''}。"
                    f"请深入分析这个话题，结合行业背景和受众兴趣，"
                    f"产出一篇有深度、有观点、适合公众号传播的文章。"
                ),
                account_id=None,
                prompt_template="",
                image_style="现代简约风格，色彩鲜明",
            )

    svc = ArticleService(db)
    # Combine primary hotspot with extra material IDs
    material_ids = [hotspot.id]
    if data.extra_material_ids:
        for mid in data.extra_material_ids:
            if mid != hotspot.id and mid not in material_ids:
                material_ids.append(mid)
    article = await svc.create_article_from_materials(
        agent=agent,
        material_ids=material_ids,
        style_id=data.style_id,
        prompt_template_id=data.prompt_template_id,
        user_prompt=data.user_prompt,
        mode=data.mode,
    )
    return {
        "ok": True,
        "article_id": article.id,
        "title": article.title,
    }


@router.post("/{hotspot_id}/create-article-async")
async def create_article_from_hotspot_async(
    hotspot_id: int,
    data: HotspotCreateArticleRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Create article asynchronously via Task system. Returns task_id immediately.

    Frontend should redirect to /create?task_id=xxx and connect to SSE for progress.
    """
    import asyncio
    from agent_publisher.database import async_session_factory
    from agent_publisher.models.task import Task
    from datetime import datetime, timezone

    hotspot = await db.get(CandidateMaterial, hotspot_id)
    if not hotspot or hotspot.source_type != "trending":
        raise HTTPException(status_code=404, detail="Hotspot not found")

    agent: Agent | None = None
    if data.agent_id:
        agent = await db.get(Agent, data.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
    else:
        builtin_result = await db.execute(select(Agent).where(Agent.is_builtin.is_(True)).limit(1))
        agent = builtin_result.scalar_one_or_none()
        if agent is None:
            platform = (hotspot.extra_metadata or {}).get("platform_name", "")
            agent = Agent(
                id=None,
                name="默认写作身份",
                topic=hotspot.title[:40],
                description=(
                    f"你是一个专注于热点话题的公众号内容编辑。"
                    f"当前话题「{hotspot.title}」"
                    f"{'来自' + platform if platform else ''}。"
                    f"请深入分析这个话题，结合行业背景和受众兴趣，"
                    f"产出一篇有深度、有观点、适合公众号传播的文章。"
                ),
                account_id=None,
                prompt_template="",
                image_style="现代简约风格，色彩鲜明",
            )

    # Create task record
    task = Task(
        agent_id=agent.id if agent and agent.id else None,
        task_type="hotspot_create",
        status="pending",
        result={
            "hotspot_id": hotspot_id,
            "hotspot_title": hotspot.title,
            "agent_name": agent.name if agent else "默认",
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Capture params for background task
    task_id = task.id
    agent_id = agent.id if agent and agent.id else None
    # Combine primary hotspot with extra material IDs for multi-material creation
    material_ids = [hotspot.id]
    if data.extra_material_ids:
        for mid in data.extra_material_ids:
            if mid != hotspot.id and mid not in material_ids:
                material_ids.append(mid)
    style_id = data.style_id
    prompt_template_id = data.prompt_template_id
    user_prompt = data.user_prompt
    mode = data.mode

    # Serialize agent data for transient agents (no id)
    agent_data = None
    if not agent_id:
        agent_data = {
            "name": agent.name,
            "topic": agent.topic,
            "description": agent.description,
            "prompt_template": agent.prompt_template,
            "image_style": agent.image_style,
        }

    async def _execute_hotspot_create():
        async with async_session_factory() as session:
            t = await session.get(Task, task_id)
            if not t:
                return
            t.status = "running"
            t.started_at = datetime.now(timezone.utc)
            t.steps = []
            await session.commit()

            step_start_times: dict[str, str] = {}

            async def _step_cb(step_name: str, status: str, output: dict):
                finished_at = datetime.now(timezone.utc).isoformat()
                started_at = step_start_times.pop(step_name, finished_at)
                t.steps = [
                    *(t.steps or []),
                    {
                        "name": step_name,
                        "status": status,
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "output": output,
                    },
                ]
                await session.commit()
                next_map = {"material_fetch": "llm_generate", "llm_generate": "save_article"}
                if step_name in next_map:
                    step_start_times[next_map[step_name]] = datetime.now(timezone.utc).isoformat()

            async def _chunk_cb(chunk: str):
                current = t.result or {}
                t.result = {**current, "llm_partial": current.get("llm_partial", "") + chunk}
                await session.commit()

            try:
                step_start_times["material_fetch"] = datetime.now(timezone.utc).isoformat()
                await _step_cb("material_fetch", "success", {"material_ids": material_ids})

                if agent_id:
                    ag = await session.get(Agent, agent_id)
                else:
                    ag = Agent(**(agent_data or {}))

                svc = ArticleService(session)
                article = await svc.create_article_from_materials(
                    agent=ag,
                    material_ids=material_ids,
                    style_id=style_id,
                    prompt_template_id=prompt_template_id,
                    user_prompt=user_prompt,
                    mode=mode,
                    step_callback=_step_cb,
                    chunk_callback=_chunk_cb,
                )

                await _step_cb("save_article", "success", {"article_id": article.id})
                t.status = "success"
                t.result = {"article_id": article.id, "title": article.title}
            except Exception as e:
                import logging

                logging.getLogger(__name__).error("Hotspot create task %d failed: %s", task_id, e)
                t.status = "failed"
                t.result = {**(t.result or {}), "error": str(e)}

            t.finished_at = datetime.now(timezone.utc)
            await session.commit()

    asyncio.create_task(_execute_hotspot_create())

    return {
        "ok": True,
        "task_id": task_id,
        "hotspot_title": hotspot.title,
    }
