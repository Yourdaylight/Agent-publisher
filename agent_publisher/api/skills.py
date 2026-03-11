"""Skills API: OpenClaw agent connection endpoints with email-based auth."""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.config import settings
from agent_publisher.models.account import Account
from agent_publisher.models.article import Article
from agent_publisher.models.agent import Agent
from agent_publisher.models.media import MediaAsset
from agent_publisher.services.article_service import ArticleService

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


class BatchPublishRequest(BaseModel):
    article_ids: list[int]


class BatchPublishResult(BaseModel):
    article_id: int
    success: bool
    media_id: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/auth", response_model=SkillAuthResponse)
async def skill_auth(req: SkillAuthRequest, request: Request):
    """Authenticate an OpenClaw agent by email (whitelist check)."""
    email = req.email.strip().lower()

    if not settings.is_email_allowed(email):
        logger.warning("Skill auth rejected for email=%s (not in whitelist)", email)
        raise HTTPException(status_code=403, detail="Email not in whitelist")

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
            media_id = await article_svc.publish_article(article_id)
            results.append(BatchPublishResult(article_id=article_id, success=True, media_id=media_id))
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
    return [
        {
            "id": a.id,
            "agent_id": a.agent_id,
            "title": a.title,
            "digest": a.digest,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
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
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_base_url: str = ""
    prompt_template: str = ""
    image_style: str = "现代简约风格，色彩鲜明"
    schedule_cron: str = "0 8 * * *"
    is_active: bool = True


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
            "llm_provider": a.llm_provider,
            "llm_model": a.llm_model,
            "schedule_cron": a.schedule_cron,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in agents
    ]


@router.post("/agents")
async def skill_create_agent(
    data: SkillAgentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create an agent. The target account must be owned by the caller (or caller is admin)."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    # Verify account ownership
    account = await db.get(Account, data.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not is_admin and account.owner_email != email:
        raise HTTPException(status_code=403, detail="You do not own this account")

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

    # Convert Markdown to HTML if content is provided
    html_content = data.html_content
    content = data.content
    if content and not html_content:
        html_content = ArticleService._markdown_to_html(content)

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
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Publish a single article to WeChat draft box."""
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
        media_id = await article_svc.publish_article(article_id)
        return {"ok": True, "media_id": media_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Media Asset Library (Skills)
# ---------------------------------------------------------------------------

@router.get("/media")
async def skill_list_media(
    request: Request,
    tag: str = "",
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List media assets. Normal users see their own; admins see all."""
    email = _get_skill_email(request)
    is_admin = settings.is_admin(email)

    stmt = select(MediaAsset).order_by(MediaAsset.id.desc())
    if not is_admin:
        stmt = stmt.where(MediaAsset.owner_email == email)

    if tag:
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
