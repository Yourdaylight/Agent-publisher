"""Skills API: OpenClaw agent connection endpoints with email-based auth."""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_publisher.api.deps import get_db
from agent_publisher.config import settings
from agent_publisher.models.account import Account
from agent_publisher.models.article import Article
from agent_publisher.models.agent import Agent
from agent_publisher.models.media import MediaAsset
from agent_publisher.services.article_service import ArticleService
from agent_publisher.services.candidate_material_service import CandidateMaterialService
from agent_publisher.services.source_registry_service import SourceRegistryService
from agent_publisher.services.wechat_service import WeChatService
from agent_publisher.schemas.candidate_material import CandidateMaterialCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


# ---------------------------------------------------------------------------
# Token helpers (email-based, separate from the admin access_key tokens)
# ---------------------------------------------------------------------------

def _create_skill_token(email: str) -> str:
    """Create an HMAC-based token carrying the email identity."""
    secret = settings.get_jwt_secret()
    ts = str(int(time.time()))
    sig = hashlib.sha256(f"{secret}:skill:{email}:{ts}".encode()).hexdigest()
    # Use | as separator since emails contain dots
    return f"{ts}|{email}|{sig}"


def verify_skill_token(token: str) -> str | None:
    """Verify a skill token. Returns the email if valid, None otherwise."""
    try:
        parts = token.split("|")
        if len(parts) != 3:
            return None
        ts_str, email, sig = parts
        ts = int(ts_str)
        # 30-day expiry
        if time.time() - ts > 30 * 86400:
            return None
        secret = settings.get_jwt_secret()
        expected = hashlib.sha256(f"{secret}:skill:{email}:{ts_str}".encode()).hexdigest()
        if sig != expected:
            return None
        return email
    except Exception:
        return None


def _get_skill_email(request: Request) -> str:
    """Extract and verify the skill token from the request. Returns email."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing skill token")
    token = auth_header[7:]
    email = verify_skill_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired skill token")
    return email


def _require_admin(email: str) -> None:
    """Raise 403 if the email is not an admin."""
    if not settings.is_admin(email):
        raise HTTPException(status_code=403, detail="Admin privileges required")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SkillAuthRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email address")
        return v


class SkillAuthResponse(BaseModel):
    token: str
    email: str
    is_admin: bool
    message: str


class SkillAccountCreate(BaseModel):
    name: str
    appid: str
    appsecret: str


class SkillAccountOut(BaseModel):
    id: int
    name: str
    appid: str
    owner_email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillArticleCreate(BaseModel):
    """Request body for creating an article manually via skill API."""
    agent_id: int
    title: str
    digest: str = ""
    content: str = ""  # Markdown content
    html_content: str = ""  # Pre-rendered HTML (used if content is empty)
    cover_image_url: str = ""  # URL or media library path e.g. media:<id>
    status: str = "draft"
    target_account_ids: list[int] | None = None


class SkillArticleUpdate(BaseModel):
    """Request body for updating an article."""
    title: str | None = None
    digest: str | None = None
    content: str | None = None
    html_content: str | None = None
    cover_image_url: str | None = None
    target_account_ids: list[int] | None = None


class ArticleAccountTargetRequest(BaseModel):
    target_account_ids: list[int] | None = None


class BatchPublishRequest(BaseModel):
    article_ids: list[int]
    target_account_ids: list[int] | None = None


class BatchPublishResult(BaseModel):
    article_id: int
    success: bool
    media_id: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

SETUP_GUIDE = {
    "title": "微信公众号快速配置指南",
    "description": "从零开始完成微信公众号注册、密钥获取和 Agent Publisher 配置的完整步骤",
    "steps": [
        {
            "step": 1,
            "title": "注册公众号",
            "url": "https://mp.weixin.qq.com/cgi-bin/readtemplate?t=register/step1_tmpl&lang=zh_CN",
            "instructions": [
                "访问上方链接，点击注册",
                "按照页面提示完成：基本信息 → 选择类型 → 信息登记 → 公众号信息",
                "个人推荐选「订阅号」（每天可群发1次），企业推荐「服务号」",
            ],
            "note": "订阅号：每天1次群发、个人/企业可注册、基础接口；服务号：每月4次群发、仅企业/组织、高级接口（支付等）",
        },
        {
            "step": 2,
            "title": "获取开发者密钥（AppID 和 AppSecret）",
            "url": "https://developers.weixin.qq.com/console/product/mp",
            "instructions": [
                "登录微信开发者平台（上方链接）",
                "左侧菜单选择「我的业务与服务」→「公众号」",
                "在「基础信息」页面复制 AppID",
                "点击 AppSecret 旁的「重置」获取密钥（仅显示一次，立即保存！）",
            ],
            "note": "AppSecret 重置后旧的密钥立即失效，请妥善保管",
        },
        {
            "step": 3,
            "title": "配置 IP 白名单",
            "instructions": [
                "在「基础信息」页面找到「API IP白名单」，点击「编辑」",
                "将服务器公网 IP `{host}` 添加到白名单中".format(host=settings.get_server_host()),
            ],
            "note": "此地址 (`{host}`) 是当前服务端配置值；如配置了域名请填对应服务器的公网 IP".format(host=settings.get_server_host()),
        },
        {
            "step": 4,
            "title": "通过 API 添加公众号到 Agent Publisher",
            "instructions": [
                "调用 POST /api/skills/auth 进行邮箱认证，获取 token",
                "调用 POST /api/skills/accounts 创建公众号，传入 name、appid、appsecret",
            ],
            "api_examples": {
                "auth": {
                    "method": "POST",
                    "path": "/api/skills/auth",
                    "body": {"email": "your@email.com"},
                },
                "create_account": {
                    "method": "POST",
                    "path": "/api/skills/accounts",
                    "headers": {"Authorization": "Bearer <token>"},
                    "body": {"name": "公众号名称", "appid": "your_appid", "appsecret": "your_appsecret"},
                },
            },
        },
        {
            "step": 5,
            "title": "创建 Agent",
            "instructions": [
                "调用 POST /api/skills/agents 创建 Agent",
                "指定 account_id（第4步创建的公众号ID）、name、topic 和 rss_sources",
            ],
            "api_examples": {
                "create_agent": {
                    "method": "POST",
                    "path": "/api/skills/agents",
                    "headers": {"Authorization": "Bearer <token>"},
                    "body": {
                        "account_id": 1,
                        "name": "科技前沿观察员",
                        "topic": "AI与科技",
                        "rss_sources": [{"url": "https://feeds.example.com/tech", "name": "Tech Feed"}],
                    },
                },
            },
        },
        {
            "step": 6,
            "title": "生成并发布文章",
            "instructions": [
                "调用 POST /api/skills/agents/{id}/generate 触发文章生成",
                "调用 GET /api/skills/articles 查看生成的文章列表",
                "调用 POST /api/skills/articles/{id}/publish 发布到微信草稿箱",
            ],
            "api_examples": {
                "generate": {
                    "method": "POST",
                    "path": "/api/skills/agents/1/generate",
                    "headers": {"Authorization": "Bearer <token>"},
                },
                "list_articles": {
                    "method": "GET",
                    "path": "/api/skills/articles",
                    "headers": {"Authorization": "Bearer <token>"},
                },
                "publish": {
                    "method": "POST",
                    "path": "/api/skills/articles/1/publish",
                    "headers": {"Authorization": "Bearer <token>"},
                },
            },
        },
    ],
    "faq": [
        {
            "question": "调用微信 API 返回 IP 不在白名单怎么办？",
            "answer": "确保已将服务器的公网 IP 添加到微信公众号的 API IP白名单中。运行 `curl ifconfig.me` 查看当前 IP。",
        },
        {
            "question": "AppSecret 忘记了怎么办？",
            "answer": "在微信开发者平台的基础信息页面，点击 AppSecret 旁的「重置」按钮重新生成。重置后旧的 AppSecret 会立即失效。",
        },
        {
            "question": "个人订阅号也能用吗？",
            "answer": "可以。个人订阅号拥有草稿箱和群发的基础权限，Agent Publisher 的核心功能（生成文章 + 推送到草稿箱）都可以正常使用。",
        },
    ],
}


@router.get("/setup-guide")
async def skill_setup_guide():
    """Return the complete WeChat account setup guide (no auth required).

    AI agents can call this endpoint to learn how to configure a WeChat
    official account from scratch, including registration URLs, developer
    platform instructions, and step-by-step API usage examples.
    """
    return SETUP_GUIDE


@router.post("/auth", response_model=SkillAuthResponse)
async def skill_auth(req: SkillAuthRequest, request: Request):
    """Authenticate an OpenClaw agent by email (whitelist check)."""
    email = req.email.strip().lower()

    if not settings.is_email_allowed(email):
        logger.warning("Skill auth rejected for email=%s (not in whitelist)", email)
        raise HTTPException(status_code=403, detail="该邮箱不在白名单中，请联系管理员")

    token = _create_skill_token(email)
    is_admin = settings.is_admin(email)
    logger.info("Skill auth success: email=%s is_admin=%s", email, is_admin)
    return SkillAuthResponse(
        token=token,
        email=email,
        is_admin=is_admin,
        message="Authentication successful",
    )


@router.post("/accounts", response_model=SkillAccountOut)
async def skill_create_account(
    data: SkillAccountCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a WeChat official account (bound to the caller's email)."""
    email = _get_skill_email(request)

    # Check for duplicate appid
    existing = await db.execute(select(Account).where(Account.appid == data.appid))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Account with this appid already exists")

    account = Account(
        name=data.name,
        appid=data.appid,
        appsecret=data.appsecret,
        owner_email=email,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    logger.info("Skill created account id=%d name=%s for email=%s", account.id, account.name, email)
    return account


@router.get("/accounts", response_model=list[SkillAccountOut])
async def skill_list_accounts(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List WeChat accounts owned by the current user."""
    email = _get_skill_email(request)

    stmt = select(Account).where(Account.owner_email == email).order_by(Account.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/accounts/all", response_model=list[SkillAccountOut])
async def skill_list_all_accounts(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List ALL WeChat accounts (admin only)."""
    email = _get_skill_email(request)
    _require_admin(email)

    result = await db.execute(select(Account).order_by(Account.id))
    return result.scalars().all()


@router.post("/articles/batch-publish", response_model=list[BatchPublishResult])
async def skill_batch_publish(
    data: BatchPublishRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Batch-publish articles to their assigned WeChat accounts (admin only)."""
    email = _get_skill_email(request)
    _require_admin(email)

    if not data.article_ids:
        raise HTTPException(status_code=400, detail="No article IDs provided")

    article_svc = ArticleService(db)
    results: list[BatchPublishResult] = []

    for article_id in data.article_ids:
        try:
            publish_result = await article_svc.publish_article(
                article_id,
                operator=email,
                target_account_ids=data.target_account_ids,
            )
            media_id = next(
                (
                    item.wechat_media_id
                    for item in publish_result.results
                    if item.wechat_media_id
                ),
                "",
            )
            results.append(
                BatchPublishResult(
                    article_id=article_id,
                    success=publish_result.ok,
                    media_id=media_id,
                    error="" if publish_result.ok else publish_result.overall_status,
                )
            )
        except Exception as e:
            logger.error("Batch publish failed for article %d: %s", article_id, e)
            results.append(BatchPublishResult(article_id=article_id, success=False, error=str(e)))

    return results


@router.get("/articles", response_model=list[dict])
async def skill_list_articles(
    request: Request,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List articles visible to the current user (own accounts) or all (admin)."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    if is_admin:
        stmt = select(Article).order_by(Article.id.desc())
    else:
        # Only articles belonging to agents linked to the user's accounts
        stmt = (
            select(Article)
            .join(Agent, Article.agent_id == Agent.id)
            .join(Account, Agent.account_id == Account.id)
            .where(Account.owner_email == email)
            .order_by(Article.id.desc())
        )

    if status:
        stmt = stmt.where(Article.status == status)

    result = await db.execute(stmt)
    articles = result.scalars().all()

    # Batch fetch variant counts
    article_ids = [a.id for a in articles]
    variant_counts: dict[int, int] = {}
    if article_ids:
        from sqlalchemy import func as sqla_func
        variant_stmt = (
            select(Article.source_article_id, sqla_func.count(Article.id))
            .where(Article.source_article_id.in_(article_ids))
            .group_by(Article.source_article_id)
        )
        variant_result = await db.execute(variant_stmt)
        variant_counts = dict(variant_result.all())

    return [
        {
            "id": a.id,
            "agent_id": a.agent_id,
            "title": a.title,
            "digest": a.digest,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "source_article_id": a.source_article_id,
            "variant_style": a.variant_style,
            "variant_count": variant_counts.get(a.id, 0),
        }
        for a in articles
    ]


@router.get("/whoami")
async def skill_whoami(request: Request):
    """Return current skill token identity info."""
    email = _get_skill_email(request)
    return {
        "email": email,
        "is_admin": settings.is_admin(email),
    }


# ---------------------------------------------------------------------------
# Agent management (scoped by account ownership)
# ---------------------------------------------------------------------------

class SkillAgentCreate(BaseModel):
    name: str
    topic: str
    description: str = ""
    account_id: int
    rss_sources: list[dict] = []
    prompt_template: str = ""
    image_style: str = "现代简约风格，色彩鲜明"
    default_style_id: str | None = None
    schedule_cron: str = "0 8 * * *"
    is_active: bool = True


class SkillAgentUpdate(BaseModel):
    name: str | None = None
    topic: str | None = None
    description: str | None = None
    rss_sources: list[dict] | None = None
    prompt_template: str | None = None
    image_style: str | None = None
    default_style_id: str | None = None
    schedule_cron: str | None = None
    is_active: bool | None = None


@router.get("/agents")
async def skill_list_agents(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List agents. Normal users see only agents on their own accounts; admins see all."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    if is_admin:
        stmt = select(Agent).order_by(Agent.id)
    else:
        stmt = (
            select(Agent)
            .join(Account, Agent.account_id == Account.id)
            .where(Account.owner_email == email)
            .order_by(Agent.id)
        )

    result = await db.execute(stmt)
    agents = result.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "topic": a.topic,
            "description": a.description,
            "account_id": a.account_id,
            "rss_sources": a.rss_sources,
            "prompt_template": a.prompt_template,
            "image_style": a.image_style,
            "default_style_id": a.default_style_id,
            "schedule_cron": a.schedule_cron,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


@router.put("/agents/{agent_id}")
async def skill_update_agent(
    agent_id: int,
    data: SkillAgentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update an agent's configuration (ownership check)."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not is_admin:
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != email:
            raise HTTPException(status_code=403, detail="You do not own this agent's account")

    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for key, value in updates.items():
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)
    logger.info("Skill updated agent id=%d for email=%s fields=%s", agent.id, email, list(updates.keys()))
    return {
        "id": agent.id,
        "name": agent.name,
        "topic": agent.topic,
        "description": agent.description,
        "account_id": agent.account_id,
        "default_style_id": agent.default_style_id,
        "image_style": agent.image_style,
        "schedule_cron": agent.schedule_cron,
        "is_active": agent.is_active,
    }


@router.post("/agents")
async def skill_create_agent(
    data: SkillAgentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create an agent. The target account must be owned by the caller (or caller is admin)."""
    from sqlalchemy import func as sqla_func
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    # Verify account ownership
    account = await db.get(Account, data.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not is_admin and account.owner_email != email:
        raise HTTPException(status_code=403, detail="You do not own this account")

    # Enforce per-user agent limit for non-admins
    if not is_admin:
        existing_count = (
            await db.execute(
                select(sqla_func.count(Agent.id))
                .join(Account, Agent.account_id == Account.id)
                .where(Account.owner_email == email)
            )
        ).scalar() or 0
        if existing_count >= 5:
            raise HTTPException(
                status_code=403,
                detail="Agent limit reached: non-admin users may create at most 5 agents",
            )

    agent = Agent(**data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    logger.info("Skill created agent id=%d name=%s for email=%s", agent.id, agent.name, email)
    return {
        "id": agent.id,
        "name": agent.name,
        "topic": agent.topic,
        "account_id": agent.account_id,
        "schedule_cron": agent.schedule_cron,
        "is_active": agent.is_active,
    }


@router.post("/agents/{agent_id}/generate")
async def skill_generate(
    agent_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Trigger article generation for an agent (ownership check)."""
    from agent_publisher.services.task_service import TaskService

    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not is_admin:
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != email:
            raise HTTPException(status_code=403, detail="You do not own this agent's account")

    task_svc = TaskService(db)
    task = await task_svc.run_generate(agent_id)
    return {"task_id": task.id, "status": task.status}


# ---------------------------------------------------------------------------
# Collect (trending / RSS / search — no LLM required)
# ---------------------------------------------------------------------------

@router.post("/agents/{agent_id}/collect")
async def skill_collect(
    agent_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Trigger material collection for an agent (ownership check).

    This is a pure algorithmic operation — no LLM configuration is required
    on the remote server. The collected materials are returned directly so
    the caller (e.g. a local Claude instance) can process them.
    """
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not is_admin:
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != email:
            raise HTTPException(status_code=403, detail="You do not own this agent's account")

    # Run collection (pure algorithm, no LLM)
    registry_svc = SourceRegistryService(db)
    collect_result = await registry_svc.collect_for_agent(agent)
    total_collected = sum(len(ids) for ids in collect_result.values())

    # Fetch newly collected materials for this agent
    mat_svc = CandidateMaterialService(db)
    from agent_publisher.schemas.candidate_material import CandidateMaterialListParams
    materials, _total = await mat_svc.list_materials(
        CandidateMaterialListParams(agent_id=agent_id, page=1, page_size=200)
    )

    # Only return materials that were just collected (by IDs from collect_result)
    collected_ids = set()
    for ids in collect_result.values():
        collected_ids.update(ids)

    new_materials = [m for m in materials if m.id in collected_ids] if collected_ids else []

    logger.info(
        "Skill collect for agent %d (%s): %d materials by email=%s",
        agent_id, agent.name, total_collected, email,
    )

    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "total_collected": total_collected,
        "collect_summary": {k: len(v) for k, v in collect_result.items()},
        "materials": [
            {
                "id": m.id,
                "title": m.title,
                "summary": m.summary,
                "original_url": m.original_url,
                "quality_score": m.quality_score,
                "source_type": m.source_type,
                "tags": m.tags or [],
                "metadata": m.extra_metadata or {},
                "is_duplicate": m.is_duplicate,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in new_materials
        ],
    }


# ---------------------------------------------------------------------------
# Task status
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}")
async def skill_get_task(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get task status."""
    from agent_publisher.models.task import Task

    _get_skill_email(request)  # auth check
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "agent_id": task.agent_id,
        "status": task.status,
        "steps": task.steps or [],
        "result": {k: v for k, v in (task.result or {}).items() if k != "llm_partial"},
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


# ---------------------------------------------------------------------------
# Article detail & single publish
# ---------------------------------------------------------------------------

@router.get("/articles/{article_id}")
async def skill_get_article(
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get a single article detail."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check for non-admin
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": article.id,
        "agent_id": article.agent_id,
        "title": article.title,
        "digest": article.digest,
        "content": article.content,
        "html_content": article.html_content,
        "cover_image_url": article.cover_image_url,
        "wechat_media_id": article.wechat_media_id,
        "status": article.status,
        "source_article_id": article.source_article_id,
        "variant_style": article.variant_style,
        "created_at": article.created_at.isoformat() if article.created_at else None,
    }


@router.post("/articles")
async def skill_create_article(
    data: SkillArticleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create an article manually (with custom content and optional media library cover).

    - Set `cover_image_url` to `media:<id>` to use an image from the media library.
    - Set `cover_image_url` to any `http(s)://...` URL to use an external image.
    - If `content` (Markdown) is provided, it will be auto-converted to HTML.
    - If only `html_content` is provided, it will be used directly.
    """
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    # Verify agent ownership
    agent = await db.get(Agent, data.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not is_admin:
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != email:
            raise HTTPException(status_code=403, detail="You do not own this agent's account")

    # Resolve cover image from media library if needed
    cover_image_url = data.cover_image_url
    if cover_image_url.startswith("media:"):
        try:
            media_id = int(cover_image_url.split(":", 1)[1])
            asset = await db.get(MediaAsset, media_id)
            if not asset:
                raise HTTPException(status_code=404, detail=f"Media asset {media_id} not found")
            # Use the download URL so publish_article can fetch it
            cover_image_url = f"/api/media/{media_id}/download"
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid media reference. Use media:<id>")

    # Convert Markdown to HTML if content is provided (always render via wenyan)
    html_content = data.html_content
    content = data.content
    if content:
        # When Markdown content is provided, always render it via wenyan,
        # even if html_content is also provided (Markdown takes precedence)
        html_content = ArticleService._markdown_to_html(content)
    elif html_content:
        # When only html_content is provided, inject WeChat inline styles
        # so that unstyled HTML gets proper formatting for WeChat OA
        from agent_publisher.services.wechat_style_service import WeChatStyleService
        html_content = WeChatStyleService.inject_styles(html_content)

    article = Article(
        agent_id=data.agent_id,
        title=data.title,
        digest=data.digest,
        content=content,
        html_content=html_content,
        cover_image_url=cover_image_url,
        images=[],
        source_news=[],
        status=data.status,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)

    article_svc = ArticleService(db)
    await article_svc._sync_article_body_media_assets(article)
    await db.commit()
    await db.refresh(article)

    logger.info("Skill created article id=%d title=%s for email=%s", article.id, article.title, email)
    return {
        "id": article.id,
        "agent_id": article.agent_id,
        "title": article.title,
        "digest": article.digest,
        "cover_image_url": article.cover_image_url,
        "status": article.status,
        "created_at": article.created_at.isoformat() if article.created_at else None,
    }


@router.post("/articles/{article_id}/publish")
async def skill_publish_article(
    article_id: int,
    data: ArticleAccountTargetRequest | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Publish a single article to one or more WeChat draft boxes."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check for non-admin
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    article_svc = ArticleService(db)
    try:
        return await article_svc.publish_article(
            article_id,
            operator=email,
            target_account_ids=data.target_account_ids if data else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Article edit & sync
# ---------------------------------------------------------------------------

@router.put("/articles/{article_id}")
async def skill_update_article(
    article_id: int,
    data: SkillArticleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update article fields (title, digest, content, html_content, cover_image_url).

    When Markdown content is modified, html_content is automatically re-rendered
    via wenyan.
    """
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Resolve cover image from media library if needed
    cover = updates.get("cover_image_url")
    if cover and cover.startswith("media:"):
        try:
            media_id = int(cover.split(":", 1)[1])
            asset = await db.get(MediaAsset, media_id)
            if not asset:
                raise HTTPException(status_code=404, detail=f"Media asset {media_id} not found")
            updates["cover_image_url"] = f"/api/media/{media_id}/download"
        except (ValueError, IndexError):
            raise HTTPException(status_code=400, detail="Invalid media reference. Use media:<id>")

    article_svc = ArticleService(db)
    try:
        updated = await article_svc.update_article(article_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "id": updated.id,
        "agent_id": updated.agent_id,
        "title": updated.title,
        "digest": updated.digest,
        "content": updated.content,
        "html_content": updated.html_content,
        "cover_image_url": updated.cover_image_url,
        "wechat_media_id": updated.wechat_media_id,
        "status": updated.status,
        "created_at": updated.created_at.isoformat() if updated.created_at else None,
    }


@router.post("/articles/{article_id}/sync")
async def skill_sync_article(
    article_id: int,
    data: ArticleAccountTargetRequest | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Sync local article edits to one or more WeChat draft boxes."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    article_svc = ArticleService(db)
    try:
        return await article_svc.sync_article_to_draft(
            article_id,
            operator=email,
            target_account_ids=data.target_account_ids if data else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"WeChat sync failed: {e}")


# ---------------------------------------------------------------------------
# Slideshow generation (Skills)
# ---------------------------------------------------------------------------

class SkillSlideshowRequest(BaseModel):
    skip_review: bool = False


@router.post("/articles/{article_id}/slideshow")
async def skill_generate_slideshow(
    article_id: int,
    data: SkillSlideshowRequest | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a slideshow task for an article (ownership check).

    Parameters:
    - skip_review: skip draft review and generate immediately (default false)
    """
    import asyncio
    from agent_publisher.services.task_service import TaskService
    from agent_publisher.database import async_session_factory

    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    skip_review = data.skip_review if data else False

    task_svc = TaskService(db)
    task = await task_svc.create_task(None, "slideshow_generate")

    async def _bg_execute_full(task_id: int, art_id: int) -> None:
        async with async_session_factory() as session:
            from agent_publisher.extensions.slideshow.service import run_chapter_pipeline
            await run_chapter_pipeline(task_id, art_id, session)

    async def _bg_execute_outline(task_id: int, art_id: int) -> None:
        async with async_session_factory() as session:
            from agent_publisher.extensions.slideshow.service import run_generate_outline
            await run_generate_outline(task_id, art_id, session)

    if skip_review:
        asyncio.create_task(_bg_execute_full(task.id, article_id))
    else:
        asyncio.create_task(_bg_execute_outline(task.id, article_id))

    mode = "skip_review" if skip_review else "draft_review"
    logger.info(
        "Skill slideshow for article %d: task=%d mode=%s by email=%s",
        article_id, task.id, mode, email,
    )
    return {"task_id": task.id, "mode": mode}


@router.get("/articles/{article_id}/slideshow/{task_id}")
async def skill_slideshow_status(
    article_id: int,
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get slideshow task status and draft content."""
    from pathlib import Path
    from agent_publisher.models.task import Task

    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = task.result or {}
    has_player = bool(result.get("concat_path") and Path(str(result.get("concat_path", ""))).exists())
    has_timeline = bool(result.get("timeline_path") and Path(str(result.get("timeline_path", ""))).exists())

    response = {
        "task_id": task.id,
        "article_id": article_id,
        "status": task.status,
        "steps": task.steps or [],
        "error": result.get("error"),
        "chapter_count": result.get("chapter_count", 0),
        "has_player": has_player,
        "has_timeline": has_timeline,
        "chapters": result.get("chapters", []),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }

    # Include draft data if available
    if task.status in ("draft_ready", "success"):
        orchestrator_output = result.get("orchestrator_output")
        if orchestrator_output:
            response["orchestrator_output"] = orchestrator_output
        slides_draft = result.get("slides_draft")
        if slides_draft:
            response["slides_draft"] = slides_draft
            response["slide_count"] = len(slides_draft)

    return response


# ---------------------------------------------------------------------------
# Media Asset Library (Skills)
# ---------------------------------------------------------------------------

@router.get("/media")
async def skill_list_media(
    request: Request,
    tag: str = "",
    source_kind: str = "",
    article_id: int | None = None,
    account_id: int | None = None,
    upload_status: str = "",
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List media assets with pagination. Normal users see their own; admins see all."""
    from agent_publisher.api.media import _serialize_media_asset

    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    stmt = select(MediaAsset).options(selectinload(MediaAsset.wechat_mappings)).order_by(MediaAsset.id.desc())
    count_stmt = select(func.count(MediaAsset.id))

    if not is_admin:
        stmt = stmt.where(MediaAsset.owner_email == email)
        count_stmt = count_stmt.where(MediaAsset.owner_email == email)

    if tag:
        stmt = stmt.where(MediaAsset.tags.contains(tag))
        count_stmt = count_stmt.where(MediaAsset.tags.contains(tag))

    if source_kind:
        stmt = stmt.where(MediaAsset.source_kind == source_kind)
        count_stmt = count_stmt.where(MediaAsset.source_kind == source_kind)

    if article_id is not None:
        stmt = stmt.where(MediaAsset.article_id == article_id)
        count_stmt = count_stmt.where(MediaAsset.article_id == article_id)

    if account_id is not None:
        stmt = stmt.where(MediaAsset.wechat_mappings.any(account_id=account_id))
        count_stmt = count_stmt.where(MediaAsset.wechat_mappings.any(account_id=account_id))

    if upload_status:
        stmt = stmt.where(MediaAsset.wechat_mappings.any(upload_status=upload_status))
        count_stmt = count_stmt.where(MediaAsset.wechat_mappings.any(upload_status=upload_status))

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    assets = result.scalars().all()

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    return {
        "items": [_serialize_media_asset(a) for a in assets],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/media")
async def skill_upload_media(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Upload a media asset via multipart form or base64 JSON.

    Multipart: POST with file field.
    JSON: POST with {"filename": "...", "data_base64": "...", "tags": [...], "description": "..."}.
    """
    import base64
    import uuid
    from pathlib import Path
    from agent_publisher.api.media import UPLOAD_DIR, ALLOWED_TYPES, MAX_FILE_SIZE

    email = _get_skill_email(request)
    content_type_header = request.headers.get("content-type", "")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if "multipart/form-data" in content_type_header:
        # Handle multipart upload
        from fastapi import UploadFile
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=400, detail="No file field in form data")

        file_content_type = file.content_type or "application/octet-stream"
        if file_content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported type: {file_content_type}")

        content = await file.read()
        original_filename = file.filename or "unnamed"
        tags_str = form.get("tags", "")
        description = form.get("description", "")
        tag_list = [t.strip() for t in str(tags_str).split(",") if t.strip()] if tags_str else []
    else:
        # Handle JSON upload (base64-encoded)
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Expected multipart/form-data or JSON body")

        data_b64 = body.get("data_base64", "")
        if not data_b64:
            raise HTTPException(status_code=400, detail="Missing data_base64 field")

        try:
            content = base64.b64decode(data_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 data")

        original_filename = body.get("filename", "unnamed.png")
        file_content_type = body.get("content_type", "image/png")
        tag_list = body.get("tags", [])
        description = body.get("description", "")

    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large ({file_size} bytes)")
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    ext = Path(original_filename).suffix or ".png"
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / stored_filename).write_bytes(content)

    asset = MediaAsset(
        filename=original_filename,
        stored_filename=stored_filename,
        content_type=file_content_type if "multipart" not in content_type_header else file_content_type,
        file_size=file_size,
        tags=tag_list,
        description=description,
        owner_email=email,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    logger.info("Skill media uploaded: id=%d filename=%s email=%s", asset.id, original_filename, email)
    return {
        "id": asset.id,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "file_size": asset.file_size,
        "tags": asset.tags,
        "description": asset.description,
        "url": f"/api/media/{asset.id}/download",
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.delete("/media/{media_id}")
async def skill_delete_media(
    media_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete a media asset (own assets or admin)."""
    from pathlib import Path
    from agent_publisher.api.media import UPLOAD_DIR

    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    asset = await db.get(MediaAsset, media_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    if not is_admin and asset.owner_email != email:
        raise HTTPException(status_code=403, detail="Access denied")

    file_path = UPLOAD_DIR / asset.stored_filename
    if file_path.is_file():
        file_path.unlink()

    await db.delete(asset)
    await db.commit()
    logger.info("Skill media deleted: id=%d email=%s", media_id, email)
    return {"ok": True, "deleted_id": media_id}


# ---------------------------------------------------------------------------
# Data Statistics (Followers & Article Stats)
# ---------------------------------------------------------------------------

async def _get_account_with_token(
    account_id: int,
    email: str,
    db: AsyncSession,
) -> Account:
    """Helper: get account, check ownership, refresh token if needed."""
    is_admin = settings.is_admin(email)
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not is_admin and account.owner_email != email:
        raise HTTPException(status_code=403, detail="Access denied")

    # Refresh token if needed
    now = datetime.now(tz=timezone.utc)
    token_expired = (
        not account.access_token
        or not account.token_expires_at
        or account.token_expires_at.replace(
            tzinfo=timezone.utc
        ) < now
    )
    if token_expired:
        token, expires_at = await WeChatService.get_access_token(
            account.appid, account.appsecret
        )
        account.access_token = token
        account.token_expires_at = expires_at
        await db.commit()

    return account


@router.get("/accounts/{account_id}/followers")
async def skill_get_followers(
    account_id: int,
    request: Request,
    begin_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get follower overview: subscribe/unsubscribe trends and cumulative count.

    Query params:
    - begin_date: YYYY-MM-DD (default: 7 days ago)
    - end_date: YYYY-MM-DD (default: yesterday)
    """
    from datetime import date, timedelta, timezone

    email = _get_skill_email(request)
    account = await _get_account_with_token(account_id, email, db)

    # Default to last 7 days (WeChat stats are available up to yesterday)
    if not end_date:
        end_date = (date.today() - timedelta(days=1)).isoformat()
    if not begin_date:
        begin_date = (date.fromisoformat(end_date) - timedelta(days=6)).isoformat()

    warnings: list[str] = []

    # Follower list (may not be available for uncertified accounts)
    followers_info: dict = {}
    try:
        followers_info = await WeChatService.get_followers(account.access_token)
    except RuntimeError as e:
        msg = str(e)
        if "48001" in msg:
            warnings.append("该公众号没有粉丝管理接口权限（需要认证服务号），无法获取粉丝总数")
        else:
            raise HTTPException(status_code=502, detail=msg)

    # Datacube stats (require certified service account)
    user_summary: list[dict] = []
    user_cumulate: list[dict] = []
    try:
        user_summary = await WeChatService.get_user_summary(
            account.access_token, begin_date, end_date
        )
        user_cumulate = await WeChatService.get_user_cumulate(
            account.access_token, begin_date, end_date
        )
    except RuntimeError as e:
        msg = str(e)
        if "48001" in msg:
            warnings.append("该公众号没有数据统计接口权限（需要认证服务号），仅返回粉丝总数")
        else:
            raise HTTPException(status_code=502, detail=msg)

    result: dict = {
        "account_id": account_id,
        "account_name": account.name,
        "begin_date": begin_date,
        "end_date": end_date,
        "total_followers": followers_info.get("total", 0),
        "user_summary": user_summary,
        "user_cumulate": user_cumulate,
    }
    if warnings:
        result["warnings"] = warnings
    return result


@router.get("/accounts/{account_id}/article-stats")
async def skill_get_article_stats(
    account_id: int,
    request: Request,
    begin_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get article statistics: daily summary and per-article detail.

    Query params:
    - begin_date: YYYY-MM-DD (default: 7 days ago)
    - end_date: YYYY-MM-DD (default: yesterday)
    """
    from datetime import date, timedelta, timezone

    email = _get_skill_email(request)
    account = await _get_account_with_token(account_id, email, db)

    if not end_date:
        end_date = (date.today() - timedelta(days=1)).isoformat()
    if not begin_date:
        begin_date = (date.fromisoformat(end_date) - timedelta(days=6)).isoformat()

    warnings: list[str] = []
    article_summary: list[dict] = []
    article_total: list[dict] = []
    try:
        article_summary = await WeChatService.get_article_summary(
            account.access_token, begin_date, end_date
        )
        article_total = await WeChatService.get_article_total(
            account.access_token, begin_date, end_date
        )
    except RuntimeError as e:
        msg = str(e)
        if "48001" in msg:
            warnings.append("该公众号没有文章统计接口权限（需要认证服务号），无法获取阅读/分享数据")
        else:
            raise HTTPException(status_code=502, detail=msg)

    result: dict = {
        "account_id": account_id,
        "account_name": account.name,
        "begin_date": begin_date,
        "end_date": end_date,
        "article_summary": article_summary,
        "article_total": article_total,
    }
    if warnings:
        result["warnings"] = warnings
    return result


# ---------------------------------------------------------------------------
# Style Preset Management (Skills)
# ---------------------------------------------------------------------------

@router.get("/style-presets")
async def skill_list_style_presets(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List all style presets (built-in + custom)."""
    from agent_publisher.services.style_preset_service import StylePresetService

    _get_skill_email(request)  # auth check
    svc = StylePresetService(db)
    presets = await svc.list_presets()
    return [
        {
            "id": p.id,
            "style_id": p.style_id,
            "name": p.name,
            "description": p.description,
            "prompt": p.prompt,
            "is_builtin": p.is_builtin,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in presets
    ]


@router.post("/style-presets")
async def skill_create_style_preset(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a custom style preset."""
    from agent_publisher.services.style_preset_service import StylePresetService

    _get_skill_email(request)  # auth check
    body = await request.json()
    style_id = body.get("style_id")
    name = body.get("name")
    if not style_id or not name:
        raise HTTPException(status_code=400, detail="style_id and name are required")

    svc = StylePresetService(db)
    try:
        preset = await svc.create_preset(
            style_id=style_id,
            name=name,
            description=body.get("description", ""),
            prompt=body.get("prompt", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "id": preset.id,
        "style_id": preset.style_id,
        "name": preset.name,
        "description": preset.description,
        "prompt": preset.prompt,
        "is_builtin": preset.is_builtin,
        "created_at": preset.created_at.isoformat() if preset.created_at else None,
    }


@router.put("/style-presets/{style_id}")
async def skill_update_style_preset(
    style_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Edit a style preset (builtin and custom are both editable)."""
    from agent_publisher.services.style_preset_service import StylePresetService

    _get_skill_email(request)  # auth check
    body = await request.json()
    updates = {k: v for k, v in body.items() if k in ("name", "description", "prompt") and v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    svc = StylePresetService(db)
    try:
        preset = await svc.update_preset(style_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "id": preset.id,
        "style_id": preset.style_id,
        "name": preset.name,
        "description": preset.description,
        "prompt": preset.prompt,
        "is_builtin": preset.is_builtin,
        "created_at": preset.created_at.isoformat() if preset.created_at else None,
    }


@router.delete("/style-presets/{style_id}")
async def skill_delete_style_preset(
    style_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom style preset. Built-in presets cannot be deleted."""
    from agent_publisher.services.style_preset_service import StylePresetService

    email = _get_skill_email(request)
    _require_admin(email)

    svc = StylePresetService(db)
    try:
        await svc.delete_preset(style_id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"ok": True, "deleted_style_id": style_id}


# ---------------------------------------------------------------------------
# Admin Management (Skills)
# ---------------------------------------------------------------------------

class AdminEmailRequest(BaseModel):
    email: str


@router.get("/admins")
async def skill_list_admins(request: Request):
    """List all admin emails (admin only)."""
    email = _get_skill_email(request)
    _require_admin(email)
    return settings.list_admins()


@router.post("/admins")
async def skill_add_admin(data: AdminEmailRequest, request: Request):
    """Add an admin at runtime (admin only).

    The new admin is also added to the email whitelist so they can authenticate.
    Runtime admins are not persisted to .env and will be lost on restart.
    """
    email = _get_skill_email(request)
    _require_admin(email)

    target_email = data.email.strip().lower()
    if not target_email or "@" not in target_email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    if settings.is_admin(target_email):
        return {"ok": True, "message": f"{target_email} is already an admin", "admins": settings.list_admins()}

    settings.add_admin(target_email)
    logger.info("Admin %s added admin %s at runtime", email, target_email)
    return {"ok": True, "message": f"{target_email} added as admin", "admins": settings.list_admins()}


@router.delete("/admins")
async def skill_remove_admin(data: AdminEmailRequest, request: Request):
    """Remove a runtime-added admin (admin only).

    Cannot remove admins configured via ADMIN_EMAILS environment variable.
    """
    email = _get_skill_email(request)
    _require_admin(email)

    target_email = data.email.strip().lower()

    # Prevent removing env-configured admins
    env_admins = set()
    if settings.admin_emails.strip():
        env_admins = {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}
    if target_email in env_admins:
        raise HTTPException(
            status_code=400,
            detail=f"{target_email} is configured in ADMIN_EMAILS env and cannot be removed at runtime"
        )

    removed = settings.remove_admin(target_email)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{target_email} is not a runtime admin")

    logger.info("Admin %s removed admin %s at runtime", email, target_email)
    return {"ok": True, "message": f"{target_email} removed from admins", "admins": settings.list_admins()}


# ---------------------------------------------------------------------------
# Variant Generation (Skills)
# ---------------------------------------------------------------------------

class SkillVariantGenerateRequest(BaseModel):
    agent_ids: list[int]
    style_ids: list[str]


@router.post("/articles/{article_id}/variants")
async def skill_generate_variants(
    article_id: int,
    data: SkillVariantGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Initiate batch variant generation for an article (with ownership check)."""
    from agent_publisher.services.task_service import TaskService

    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check for source article
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    if not data.style_ids:
        raise HTTPException(status_code=400, detail="At least one style_id is required")
    if not data.agent_ids:
        raise HTTPException(status_code=400, detail="At least one agent_id is required")

    # Verify the caller owns target agents (or is admin)
    if not is_admin:
        for aid in data.agent_ids:
            target_agent = await db.get(Agent, aid)
            if not target_agent:
                raise HTTPException(status_code=404, detail=f"Agent {aid} not found")
            target_account = await db.get(Account, target_agent.account_id)
            if not target_account or target_account.owner_email != email:
                raise HTTPException(status_code=403, detail=f"No write access to agent {aid}")

    task_svc = TaskService(db)
    try:
        task = await task_svc.run_batch_variants(
            source_article_id=article_id,
            agent_ids=data.agent_ids,
            style_ids=data.style_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "batch_task_id": task.id, "total": len(data.agent_ids)}


@router.get("/articles/{article_id}/variants")
async def skill_list_article_variants(
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List all variant articles derived from the given source article."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Ownership check
    if not is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != email:
                raise HTTPException(status_code=403, detail="Access denied")

    stmt = (
        select(Article)
        .where(Article.source_article_id == article_id)
        .order_by(Article.id.desc())
    )
    result = await db.execute(stmt)
    variants = result.scalars().all()

    # Batch-load agent names
    agent_ids = list({v.agent_id for v in variants})
    agent_names: dict[int, str] = {}
    if agent_ids:
        agent_result = await db.execute(
            select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids))
        )
        agent_names = dict(agent_result.all())

    return [
        {
            "id": v.id,
            "agent_id": v.agent_id,
            "agent_name": agent_names.get(v.agent_id, ""),
            "title": v.title,
            "digest": v.digest,
            "status": v.status,
            "variant_style": v.variant_style,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in variants
    ]


# ---------------------------------------------------------------------------
# Skills feed: accept candidate materials from external skills
# ---------------------------------------------------------------------------

class SkillsFeedItem(BaseModel):
    """Schema for a candidate material submitted by a skill."""
    title: str
    summary: str = ""
    original_url: str = ""
    raw_content: str = ""
    tags: list[str] = []
    metadata: dict | None = None


@router.post("/agents/{agent_id}/feed")
async def submit_skill_feed(
    agent_id: int,
    items: list[SkillsFeedItem],
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Accept candidate materials from an external skill for a given agent.

    Requires a valid skill token in the Authorization header.
    Validates the skill identity against the agent's allowed_skill_sources whitelist.
    """
    # Authenticate skill token
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header
    email = verify_skill_token(token)
    if not email:
        raise HTTPException(401, "Invalid or expired skill token")

    # Fetch agent
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Check allowed_skill_sources whitelist
    if agent.allowed_skill_sources:
        if email not in agent.allowed_skill_sources:
            raise HTTPException(
                403,
                f"Skill '{email}' is not in the allowed sources for this agent",
            )

    # Validate and ingest each item
    material_svc = CandidateMaterialService(db)
    created_ids: list[int] = []
    errors: list[dict] = []

    for idx, item in enumerate(items):
        # Reject items missing required metadata
        if not item.title:
            errors.append({"index": idx, "error": "title is required"})
            continue
        if not item.original_url and not item.summary:
            errors.append({"index": idx, "error": "original_url or summary is required"})
            continue

        data = CandidateMaterialCreate(
            source_type="skills_feed",
            source_identity=email,
            original_url=item.original_url,
            title=item.title,
            summary=item.summary,
            raw_content=item.raw_content,
            metadata=item.metadata,
            tags=item.tags,
            agent_id=agent_id,
        )
        material = await material_svc.ingest(data, agent_name=agent.name)
        created_ids.append(material.id)

    return {
        "ingested": len(created_ids),
        "material_ids": created_ids,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Markdown Upload (Image Proxy)
# ---------------------------------------------------------------------------

class MarkdownUploadRequest(BaseModel):
    content: str
    tags: list[str] = []


class MarkdownImageInfo(BaseModel):
    original_url: str
    media_id: int
    filename: str
    url: str


class MarkdownUploadResponse(BaseModel):
    content: str
    images: list[MarkdownImageInfo]
    images_count: int
    skipped_count: int


@router.post("/markdown", response_model=MarkdownUploadResponse)
async def skill_upload_markdown(
    body: MarkdownUploadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Upload a markdown file with remote images.

    Downloads all remote images, uploads them to the media library,
    and replaces the image URLs in the markdown with media library URLs.

    Returns the processed markdown and a list of image mappings.
    """
    from agent_publisher.services.markdown_service import MarkdownService

    email = _get_skill_email(request)

    svc = MarkdownService(db)
    processed_content, image_infos = await svc.process_markdown(
        content=body.content,
        owner_email=email,
        tags=body.tags,
    )

    skipped = 0
    total_matches = len([m for m in re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', body.content)])
    if total_matches > len(image_infos):
        skipped = total_matches - len(image_infos)

    logger.info(
        "Markdown processed: email=%s images=%d skipped=%d",
        email,
        len(image_infos),
        skipped,
    )

    return MarkdownUploadResponse(
        content=processed_content,
        images=[MarkdownImageInfo(**info) for info in image_infos],
        images_count=len(image_infos),
        skipped_count=skipped,
    )


# ---------------------------------------------------------------------------
# Delete endpoints (ownership-checked)
# ---------------------------------------------------------------------------

@router.delete("/agents/{agent_id}")
async def skill_delete_agent(
    agent_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete an agent. Caller must own the agent's account (or be admin)."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if not is_admin:
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != email:
            raise HTTPException(status_code=403, detail="You do not own this agent's account")

    await db.delete(agent)
    await db.commit()
    logger.info("Skill deleted agent id=%d by email=%s", agent_id, email)
    return {"ok": True}


@router.delete("/accounts/{account_id}")
async def skill_delete_account(
    account_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete a WeChat account. Caller must own the account (or be admin)."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not is_admin and account.owner_email != email:
        raise HTTPException(status_code=403, detail="You do not own this account")

    await db.delete(account)
    await db.commit()
    logger.info("Skill deleted account id=%d by email=%s", account_id, email)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Permission group visibility (read-only for skill users)
# ---------------------------------------------------------------------------

@router.get("/groups")
async def skill_list_my_groups(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return the groups the current user belongs to (read-only)."""
    from agent_publisher.models.group import UserGroup, UserGroupMember
    from sqlalchemy.orm import selectinload

    email = _get_skill_email(request)

    group_ids_result = await db.execute(
        select(UserGroupMember.group_id).where(UserGroupMember.email == email)
    )
    group_ids = [row[0] for row in group_ids_result.all()]

    if not group_ids:
        return []

    result = await db.execute(
        select(UserGroup)
        .where(UserGroup.id.in_(group_ids))
        .options(selectinload(UserGroup.members))
        .order_by(UserGroup.id)
    )
    groups = result.scalars().all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "member_emails": [m.email for m in g.members],
        }
        for g in groups
    ]
