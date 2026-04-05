from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_publisher.api.deps import get_db, get_current_user, get_visible_emails, UserContext
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.article_publish_relation import ArticlePublishRelation
from agent_publisher.models.publish_record import PublishRecord
from agent_publisher.schemas.article import (
    ArticleOut,
    ArticlePublishRequest,
    ArticlePublishResponse,
    ArticleSyncRequest,
    ArticleSyncResponse,
)
from agent_publisher.services.article_service import ArticleService
from agent_publisher.services.credits_service import CreditsService
from agent_publisher.services.task_service import TaskService

router = APIRouter(prefix="/api/articles", tags=["articles"])


class ArticleUpdate(BaseModel):
    """Request body for updating an article."""
    title: str | None = None
    digest: str | None = None
    content: str | None = None
    html_content: str | None = None
    cover_image_url: str | None = None


class VariantGenerateRequest(BaseModel):
    """Request body for batch variant generation."""
    agent_ids: list[int]
    style_ids: list[str]


class WorkbenchCreateRequest(BaseModel):
    material_ids: list[int]
    agent_id: int
    style_id: str | None = None
    prompt_id: int | None = None
    user_prompt: str | None = None
    mode: str | None = None


async def _get_article_with_ownership(
    article_id: int, user: UserContext, db: AsyncSession
) -> Article:
    """Fetch an article and verify ownership through Agent -> Account chain.

    A non-admin may read articles owned by themselves OR by any co-member in
    a shared permission group. Write operations (update/publish/sync) must still
    be performed by the article owner or an admin.
    """
    stmt = select(Article).where(Article.id == article_id).options(
        selectinload(Article.publish_relations).selectinload(
            ArticlePublishRelation.account
        ),
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    if not user.is_admin:
        agent = await db.get(Agent, article.agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        account = await db.get(Account, agent.account_id)
        if not account:
            raise HTTPException(403, "Access denied")
        # Allow owner OR group co-members
        visible = await get_visible_emails(user, db)
        if account.owner_email not in visible:
            raise HTTPException(403, "Access denied")
    return article


async def _get_article_own_only(
    article_id: int, user: UserContext, db: AsyncSession
) -> Article:
    """Stricter check: only the owner (or admin) may modify the article."""
    stmt = select(Article).where(Article.id == article_id).options(
        selectinload(Article.publish_relations).selectinload(
            ArticlePublishRelation.account
        ),
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    if not user.is_admin:
        agent = await db.get(Agent, article.agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != user.email:
            raise HTTPException(403, "Access denied")
    return article


@router.get("")
async def list_articles(
    agent_id: int | None = None,
    status: str | None = None,
    group_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List articles with publish_count, filtered by user ownership + permission groups."""
    stmt = select(Article).order_by(Article.id.desc())
    if not user.is_admin:
        visible_emails = await get_visible_emails(user, db)
        stmt = stmt.join(Agent, Article.agent_id == Agent.id).join(
            Account, Agent.account_id == Account.id
        ).where(Account.owner_email.in_(visible_emails))
    elif group_id is not None:
        # Admin filtering by a specific group
        from agent_publisher.models.group import UserGroupMember
        member_emails_stmt = select(UserGroupMember.email).where(
            UserGroupMember.group_id == group_id
        )
        member_emails_result = await db.execute(member_emails_stmt)
        group_emails = [row[0] for row in member_emails_result.all()]
        if group_emails:
            stmt = stmt.join(Agent, Article.agent_id == Agent.id).join(
                Account, Agent.account_id == Account.id
            ).where(Account.owner_email.in_(group_emails))
        else:
            return []
    if agent_id:
        stmt = stmt.where(Article.agent_id == agent_id)
    if status:
        stmt = stmt.where(Article.status == status)
    result = await db.execute(stmt)
    articles = result.scalars().all()

    # Batch fetch publish counts
    article_ids = [a.id for a in articles]
    publish_counts: dict[int, int] = {}
    if article_ids:
        count_stmt = (
            select(PublishRecord.article_id, func.count(PublishRecord.id))
            .where(PublishRecord.article_id.in_(article_ids))
            .group_by(PublishRecord.article_id)
        )
        count_result = await db.execute(count_stmt)
        publish_counts = dict(count_result.all())

    # Batch fetch variant counts
    variant_counts: dict[int, int] = {}
    if article_ids:
        variant_stmt = (
            select(Article.source_article_id, func.count(Article.id))
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
            "publish_count": publish_counts.get(a.id, 0),
            "source_article_id": a.source_article_id,
            "variant_style": a.variant_style,
            "variant_count": variant_counts.get(a.id, 0),
        }
        for a in articles
    ]


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return await _get_article_with_ownership(article_id, user, db)


@router.post("/from-materials")
async def create_article_from_materials(
    data: WorkbenchCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    agent = await db.get(Agent, data.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not user.is_admin:
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != user.email:
            raise HTTPException(403, "Access denied")
    article_svc = ArticleService(db)
    try:
        article = await article_svc.create_article_from_materials(
            agent=agent,
            material_ids=data.material_ids,
            style_id=data.style_id,
            prompt_template_id=data.prompt_id,
            user_prompt=data.user_prompt,
            mode=data.mode,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "ok": True,
        "article_id": article.id,
        "title": article.title,
        "status": article.status,
    }


@router.post("/{article_id}/beautify")
async def beautify_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Re-render article Markdown content through wenyan for beautiful formatting."""
    article = await _get_article_own_only(article_id, user, db)
    if not article.content:
        raise HTTPException(400, "文章没有 Markdown 内容，无法美化排版")

    article_svc = ArticleService(db)
    html = article_svc._markdown_to_html(article.content)
    article.html_content = html
    await db.commit()
    await db.refresh(article)

    return {
        "ok": True,
        "article_id": article.id,
        "html_content": html,
    }


@router.post("/{article_id}/ai-beautify")
async def ai_beautify_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Use LLM to beautify article HTML for WeChat formatting. Costs 3 Credits."""
    article = await _get_article_own_only(article_id, user, db)

    # Check & consume credits
    credits_svc = CreditsService(db)
    check = await credits_svc.check(user.email, cost=3)
    if not check["ok"]:
        raise HTTPException(402, f"Credits 不足，需要 3，当前 {check['available']}")

    consume_result = await credits_svc.consume(
        user_email=user.email,
        operation_type="ai_beautify",
        cost=3,
        reference_id=article_id,
        description=f"AI 美化文章 #{article_id}",
    )
    if not consume_result["ok"]:
        raise HTTPException(402, consume_result.get("error", "Credits 不足"))

    article_svc = ArticleService(db)
    try:
        html = await article_svc.ai_beautify_html(article)
    except Exception as e:
        # Refund on failure
        await credits_svc.refund(
            user_email=user.email,
            operation_type="ai_beautify",
            cost=3,
            reference_id=article_id,
        )
        raise HTTPException(500, f"AI 美化失败：{e}")

    return {
        "ok": True,
        "article_id": article.id,
        "html_content": html,
        "credits_consumed": 3,
    }

@router.post("/{article_id}/publish", response_model=ArticlePublishResponse)
async def publish_article(
    article_id: int,
    data: ArticlePublishRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    await _get_article_own_only(article_id, user, db)
    article_svc = ArticleService(db)
    try:
        operator = user.email if not user.is_admin else "admin"
        return await article_svc.publish_article(
            article_id,
            operator=operator,
            target_account_ids=data.target_account_ids if data else None,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.put("/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: int,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Update article fields (title, digest, content, html_content, cover_image_url).

    When Markdown content is modified, html_content is automatically re-rendered
    via wenyan.
    """
    await _get_article_own_only(article_id, user, db)
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    article_svc = ArticleService(db)
    try:
        await article_svc.update_article(article_id, updates)
        # Re-fetch with eager-loaded relations for response serialization
        return await _get_article_with_ownership(article_id, user, db)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{article_id}/sync", response_model=ArticleSyncResponse)
async def sync_article(
    article_id: int,
    data: ArticleSyncRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Sync local article edits to WeChat draft box."""
    await _get_article_own_only(article_id, user, db)
    article_svc = ArticleService(db)
    try:
        operator = user.email if not user.is_admin else "admin"
        return await article_svc.sync_article_to_draft(
            article_id,
            operator=operator,
            target_account_ids=data.target_account_ids if data else None,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, f"WeChat sync failed: {e}")


@router.get("/{article_id}/publish-records")
async def get_article_publish_records(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get publish records for a specific article."""
    await _get_article_with_ownership(article_id, user, db)
    stmt = (
        select(PublishRecord)
        .where(PublishRecord.article_id == article_id)
        .order_by(PublishRecord.id.desc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "article_id": r.article_id,
            "action": r.action,
            "wechat_media_id": r.wechat_media_id,
            "status": r.status,
            "operator": r.operator,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.post("/{article_id}/generate-cover")
async def generate_cover_image(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Generate a cover image for an article using AI. Costs 1 Credit."""
    article = await _get_article_own_only(article_id, user, db)

    credits_svc = CreditsService(db)
    check = await credits_svc.check(user.email, cost=1)
    if not check["ok"]:
        raise HTTPException(402, f"Credits 不足，需要 1，当前 {check['available']}")

    consume_result = await credits_svc.consume(
        user_email=user.email,
        operation_type="generate_cover",
        cost=1,
        reference_id=article_id,
        description=f"生成封面图 #{article_id}",
    )
    if not consume_result["ok"]:
        raise HTTPException(402, consume_result.get("error", "Credits 不足"))

    from agent_publisher.services.image_service import HunyuanImageService
    image_svc = HunyuanImageService()

    # Build a safe image prompt from article title/digest
    title = article.title or "科技资讯"
    prompt = (
        f"一张精美的现代简约风格插画，主题是：{title[:50]}，"
        "适合作为公众号文章封面，无任何文字，色彩鲜明，高质量数字艺术。"
    )

    try:
        cover_url = await image_svc.generate_image(prompt, "1024:1024")
    except Exception as e:
        await credits_svc.refund(
            user_email=user.email,
            operation_type="generate_cover",
            cost=1,
            reference_id=article_id,
        )
        raise HTTPException(500, f"封面图生成失败：{e}")

    article.cover_image_url = cover_url
    await db.commit()
    await db.refresh(article)

    return {
        "ok": True,
        "article_id": article.id,
        "cover_image_url": cover_url,
        "credits_consumed": 1,
    }


@router.post("/{article_id}/variants")
async def generate_variants(
    article_id: int,
    data: VariantGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Initiate batch variant generation for an article."""
    await _get_article_with_ownership(article_id, user, db)

    if not data.style_ids:
        raise HTTPException(400, "At least one style_id is required")
    if not data.agent_ids:
        raise HTTPException(400, "At least one agent_id is required")

    task_svc = TaskService(db)
    try:
        task = await task_svc.run_batch_variants(
            source_article_id=article_id,
            agent_ids=data.agent_ids,
            style_ids=data.style_ids,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"ok": True, "batch_task_id": task.id, "total": len(data.agent_ids)}


@router.get("/{article_id}/variants")
async def list_article_variants(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List all variant articles derived from the given source article."""
    await _get_article_with_ownership(article_id, user, db)

    from agent_publisher.models.agent import Agent

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
