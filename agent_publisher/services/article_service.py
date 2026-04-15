from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.article_publish_relation import ArticlePublishRelation
from agent_publisher.models.candidate_material import CandidateMaterial
from agent_publisher.models.media import MediaAsset, MediaAssetWechatMapping
from agent_publisher.models.publish_record import PublishRecord
from agent_publisher.schemas.article import (
    AccountScopedPublishResult,
    ArticlePublishResponse,
    ArticleSyncResponse,
)
from agent_publisher.services.candidate_material_service import CandidateMaterialService
from agent_publisher.services.image_service import HunyuanImageService
from agent_publisher.services.llm_service import LLMService
from agent_publisher.services.rss_service import RSSService
from agent_publisher.services.wechat_service import WeChatService
from agent_publisher.services.prompt_template_service import PromptTemplateService
from agent_publisher.services.style_preset_service import StylePresetService

logger = logging.getLogger(__name__)


class ArticleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.rss = RSSService()
        self.llm = LLMService()
        self.image = HunyuanImageService()

    async def generate_article(
        self,
        agent: Agent,
        step_callback: Callable[..., Awaitable[None]] | None = None,
        chunk_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> Article:
        """Full pipeline: CandidateMaterial pool (or RSS fallback) -> LLM -> Image -> Article.

        When the agent has pending candidate materials in the pool, those are
        consumed first. Otherwise falls back to the legacy direct RSS fetch.

        Args:
            agent: The agent to generate an article for.
            step_callback: Optional async callback invoked after each step.
                Signature: (step_name: str, status: str, output: dict) -> None
            chunk_callback: Optional async callback for streaming LLM chunks.
                Signature: (chunk: str) -> None
        """
        logger.info("Generating article for agent=%s topic=%s", agent.name, agent.topic)

        # 1. Try to consume from CandidateMaterial pool first
        material_svc = CandidateMaterialService(self.session)
        materials = await material_svc.list_pending_for_agent(agent.id, limit=15)
        consumed_material_ids: list[int] = []

        # If pool is empty, try on-demand collection via source registry
        if not materials:
            try:
                from agent_publisher.services.source_registry_service import SourceRegistryService
                registry = SourceRegistryService(self.session)
                collect_result = await registry.collect_for_agent(agent)
                total_collected = sum(len(ids) for ids in collect_result.values())
                if total_collected > 0:
                    logger.info("On-demand collection yielded %d materials for agent %s", total_collected, agent.name)
                    materials = await material_svc.list_pending_for_agent(agent.id, limit=15)
            except Exception as e:
                logger.warning("On-demand collection failed for agent %s: %s", agent.name, e)

        if materials:
            # Use candidate materials as news source
            news_text = "\n".join(
                f"- [{m.title}]({m.original_url})\n  {m.summary[:200]}"
                for m in materials
            )
            source_news = [
                {
                    "title": m.title,
                    "link": m.original_url,
                    "source": m.source_identity,
                    "material_id": m.id,
                }
                for m in materials
            ]
            consumed_material_ids = [m.id for m in materials]

            if step_callback:
                await step_callback(
                    "material_fetch",
                    "success",
                    {
                        "count": len(materials),
                        "source": "candidate_materials",
                        "titles": [m.title for m in materials],
                    },
                )
        else:
            # Fallback: fetch RSS directly (legacy path)
            news_items = await self.rss.fetch_agent_feeds(agent.rss_sources or [])
            if not news_items:
                logger.warning("No news items found for agent %s", agent.name)

            news_text = "\n".join(
                f"- [{item.title}]({item.link})\n  {item.summary[:200]}"
                for item in news_items[:15]
            )
            source_news = [
                {"title": item.title, "link": item.link, "source": item.source_name}
                for item in news_items[:15]
            ]

            if step_callback:
                await step_callback(
                    "rss_fetch",
                    "success",
                    {
                        "count": len(news_items),
                        "source": "rss_direct",
                        "titles": [item.title for item in news_items[:15]],
                    },
                )

        # 2. Generate article via LLM (streaming when chunk_callback is provided)
        # Always use platform-level LLM config from settings
        from agent_publisher.config import settings

        provider = settings.default_llm_provider
        model = settings.default_llm_model
        api_key = settings.default_llm_api_key
        base_url = settings.default_llm_base_url

        messages = self.llm.build_article_messages(
            topic=agent.topic,
            news_list=news_text,
            prompt_template=agent.prompt_template or "",
            agent_description=agent.description or "",
        )

        if chunk_callback:
            # Use streaming mode
            raw_response = ""
            stream = self.llm.generate_stream(
                provider=provider,
                model=model,
                api_key=api_key,
                messages=messages,
                base_url=base_url,
            )
            async for chunk in stream:
                raw_response += chunk
                await chunk_callback(chunk)
        else:
            raw_response = await self.llm.generate(
                provider=provider,
                model=model,
                api_key=api_key,
                messages=messages,
                base_url=base_url,
            )

        parsed = self.llm.parse_article_response(raw_response)

        if step_callback:
            await step_callback(
                "llm_generate",
                "success",
                {
                    "title": parsed.get("title", ""),
                    "content_length": len(parsed.get("content", "")),
                    "provider": provider,
                    "model": model,
                },
            )

        # 3. Generate cover image
        cover_image_url = ""
        image_prompt = ""
        image_status = "skipped"
        try:
            # Use agent topic/style instead of article title to avoid
            # triggering Tencent Cloud content-safety filters on news headlines.
            style_desc = agent.image_style or "现代简约风格"
            topic_desc = agent.topic or "科技资讯"
            image_prompt = (
                f"一张精美的{style_desc}插画，主题是{topic_desc}，"
                "适合作为公众号文章封面，无任何文字，色彩鲜明，高质量数字艺术。"
            )
            cover_image_url = await self.image.generate_image(image_prompt, "1024:1024")
            image_status = "success"
        except Exception as e:
            logger.error("Cover image generation failed: %s", e)
            image_status = "failed"

        if step_callback:
            await step_callback(
                "image_generate",
                image_status,
                {"prompt": image_prompt, "has_image": bool(cover_image_url)},
            )

        # 4. Convert Markdown to simple HTML
        html_content = self._markdown_to_html(parsed["content"])

        # 5. Save article
        article = Article(
            agent_id=agent.id,
            title=parsed["title"],
            digest=parsed["digest"],
            content=parsed["content"],
            html_content=html_content,
            cover_image_url=cover_image_url,
            images=[],
            source_news=source_news,
            status="draft",
        )
        self.session.add(article)
        await self.session.commit()
        await self.session.refresh(article)

        await self._sync_article_body_media_assets(article)
        await self.session.commit()
        await self.session.refresh(article)

        # Mark consumed materials as accepted
        for mid in consumed_material_ids:
            await material_svc.mark_accepted(mid)

        if step_callback:
            await step_callback(
                "save_article",
                "success",
                {"article_id": article.id, "title": article.title},
            )

        logger.info("Article created: id=%d title=%s", article.id, article.title)
        return article

    async def create_article_from_materials(
        self,
        *,
        agent: Agent,
        material_ids: list[int],
        style_id: str | None = None,
        prompt_template_id: int | None = None,
        user_prompt: str | None = None,
        mode: str | None = None,
        step_callback: Callable[..., Awaitable[None]] | None = None,
        chunk_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> Article:
        stmt = select(CandidateMaterial).where(CandidateMaterial.id.in_(material_ids)).order_by(CandidateMaterial.created_at.desc())
        result = await self.session.execute(stmt)
        materials = list(result.scalars().all())
        if not materials:
            raise ValueError("No materials found")

        title_seed = materials[0].title
        digest_seed = materials[0].summary or materials[0].title

        # Build combined content from materials, with per-item truncation
        # to avoid exceeding LLM context limits
        MAX_PER_ITEM = 3000
        combined_content = "\n\n".join(
            f"标题：{item.title}\n摘要：{item.summary}\n正文：{(item.raw_content or item.summary or '')[:MAX_PER_ITEM]}\n来源：{item.original_url}"
            for item in materials
        )
        # Hard cap on total content length (roughly 8000 tokens worth)
        MAX_TOTAL = 12000
        if len(combined_content) > MAX_TOTAL:
            combined_content = combined_content[:MAX_TOTAL] + "\n\n[...素材已截断，请基于以上内容撰写文章]"

        prompt_text = agent.prompt_template or ""
        if prompt_template_id:
            prompt_service = PromptTemplateService(self.session)
            prompt_template = await prompt_service.get_template(prompt_template_id)
            if prompt_template:
                prompt_text = prompt_template.content
                await prompt_service.increment_usage(prompt_template_id)

        if style_id:
            style_service = StylePresetService(self.session)
            style = await style_service.get_preset(style_id)
            if style and style.prompt:
                prompt_text = f"{prompt_text}\n\n附加风格要求：\n{style.prompt}" if prompt_text else style.prompt

        if user_prompt and user_prompt.strip():
            prompt_text = f"{prompt_text}\n\n用户创作指令：\n{user_prompt.strip()}" if prompt_text else user_prompt.strip()

        # Apply creation mode instructions
        mode_instructions = {
            "rewrite": "创作模式：爆款二创。基于以下素材进行二次创作，保留核心信息但用全新的角度和更吸引人的方式重新表达。",
            "summary": "创作模式：热点总结。从多个信源角度综合总结以下素材，提炼关键信息，给出全面客观的概述。",
            "expand": "创作模式：观点扩写。基于以下素材展开深度分析，加入独到观点、行业洞察和前瞻性判断。",
        }
        if mode and mode in mode_instructions:
            mode_text = mode_instructions[mode]
            prompt_text = f"{prompt_text}\n\n{mode_text}" if prompt_text else mode_text

        from agent_publisher.config import settings
        messages = self.llm.build_article_messages(
            topic=agent.topic,
            news_list=combined_content,
            prompt_template=prompt_text,
            agent_description=agent.description or "",
        )

        if chunk_callback:
            # Streaming mode
            raw_response = ""
            if step_callback:
                await step_callback("llm_generate", "running", {"provider": settings.default_llm_provider, "model": settings.default_llm_model})
            stream = self.llm.generate_stream(
                provider=settings.default_llm_provider,
                model=settings.default_llm_model,
                api_key=settings.default_llm_api_key,
                messages=messages,
                base_url=settings.default_llm_base_url,
            )
            async for chunk in stream:
                raw_response += chunk
                await chunk_callback(chunk)
        else:
            raw_response = await self.llm.generate(
                provider=settings.default_llm_provider,
                model=settings.default_llm_model,
                api_key=settings.default_llm_api_key,
                messages=messages,
                base_url=settings.default_llm_base_url,
            )
        parsed = self.llm.parse_article_response(raw_response)
        if step_callback:
            await step_callback("llm_generate", "success", {
                "title": parsed.get("title", ""),
                "content_length": len(parsed.get("content", "")),
            })
        final_title = parsed.get("title") or title_seed
        final_digest = parsed.get("digest") or digest_seed[:180]
        final_content = parsed.get("content") or combined_content
        html_content = self._markdown_to_html(final_content)

        article = Article(
            agent_id=agent.id if (agent and agent.id) else None,
            title=final_title,
            digest=final_digest,
            content=final_content,
            html_content=html_content,
            cover_image_url="",
            images=[],
            source_news=[
                {
                    "title": item.title,
                    "link": item.original_url,
                    "source": item.source_identity,
                    "material_id": item.id,
                }
                for item in materials
            ],
            status="draft",
            variant_style=style_id,
        )
        self.session.add(article)
        await self.session.commit()
        await self.session.refresh(article)
        await self._sync_article_body_media_assets(article)
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def publish_article(
        self,
        article_id: int,
        operator: str = 'admin',
        target_account_ids: list[int] | None = None,
    ) -> ArticlePublishResponse:
        """Publish an article to one or more WeChat draft boxes."""
        article, agent = await self._get_article_and_agent(article_id)
        accounts = await self._resolve_target_accounts(agent, target_account_ids)
        now = datetime.now(timezone.utc)
        publish_html = await self._get_publish_html(article)

        results: list[AccountScopedPublishResult] = []
        primary_media_id = ''
        published_any = False

        for account in accounts:
            relation = await self._get_or_create_relation(article.id, account.id)
            relation.publish_status = 'processing'
            relation.last_error = ''
            await self.session.flush()

            try:
                access_token = await self._ensure_account_access_token(account)
                thumb_media_id = await self._upload_cover_thumb(article, access_token)
                if not thumb_media_id:
                    raise RuntimeError(
                        'No thumb_media_id available. '
                        'Please set a cover image or ensure the article has body images.'
                    )
                scoped_html = await self._rewrite_wechat_body_images(
                    account=account,
                    access_token=access_token,
                    html_content=publish_html,
                    article_id=article.id,
                )
                draft_article = self._build_wechat_draft_article(
                    article=article,
                    agent=agent,
                    html_content=scoped_html,
                    thumb_media_id=thumb_media_id,
                )
                media_id = await WeChatService.add_draft(access_token, [draft_article])

                relation.wechat_media_id = media_id
                relation.publish_status = 'success'
                relation.sync_status = 'synced'
                relation.last_error = ''
                relation.last_published_at = now
                relation.last_synced_at = now

                record = self._build_publish_record(
                    article_id=article.id,
                    account_id=account.id,
                    action='publish',
                    wechat_media_id=media_id,
                    status='success',
                    operator=operator,
                )
                self.session.add(record)

                results.append(
                    AccountScopedPublishResult(
                        account_id=account.id,
                        account_name=account.name,
                        status='success',
                        wechat_media_id=media_id,
                        stage='publish',
                        error='',
                    )
                )
                if not primary_media_id:
                    primary_media_id = media_id
                published_any = True
            except Exception as exc:
                logger.error(
                    'Article %d publish failed for account %d: %s',
                    article.id,
                    account.id,
                    exc,
                )
                relation.publish_status = 'failed'
                relation.last_error = str(exc)

                record = self._build_publish_record(
                    article_id=article.id,
                    account_id=account.id,
                    action='publish',
                    wechat_media_id=relation.wechat_media_id or '',
                    status='failed',
                    operator=operator,
                    error_message=str(exc),
                )
                self.session.add(record)

                results.append(
                    AccountScopedPublishResult(
                        account_id=account.id,
                        account_name=account.name,
                        status='failed',
                        wechat_media_id=relation.wechat_media_id or '',
                        stage='publish',
                        error=str(exc),
                    )
                )

        if published_any:
            article.wechat_media_id = primary_media_id
            article.status = 'published'
            article.published_at = now

        await self.session.commit()
        await self.session.refresh(article)

        overall_status = self._aggregate_result_status(results)
        logger.info(
            'Article %d publish finished: overall_status=%s targets=%s',
            article.id,
            overall_status,
            [account.id for account in accounts],
        )
        return ArticlePublishResponse(
            ok=published_any,
            article_id=article.id,
            overall_status=overall_status,
            media_id=primary_media_id,
            target_account_ids=[account.id for account in accounts],
            results=results,
        )

    async def _load_image_resource(self, image_source: str) -> tuple[bytes, str, str]:
        """Load image bytes from local media, remote URL, or data URL."""
        normalized_source = (image_source or '').strip()
        if not normalized_source:
            raise ValueError('Image source is empty')

        media_id = self._extract_media_id_from_download_url(normalized_source)
        if media_id is not None:
            from agent_publisher.api.media import UPLOAD_DIR

            media_asset = await self.session.get(MediaAsset, media_id)
            if not media_asset:
                raise ValueError(f'Media asset {media_id} not found')

            local_path = UPLOAD_DIR / media_asset.stored_filename
            if not local_path.is_file():
                raise FileNotFoundError(f'Media file not found on disk: {local_path}')

            content_type = media_asset.content_type or mimetypes.guess_type(local_path.name)[0] or 'image/jpeg'
            return local_path.read_bytes(), media_asset.filename, content_type

        if normalized_source.startswith("http://") or normalized_source.startswith("https://"):
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                img_resp = await client.get(normalized_source)
                img_resp.raise_for_status()
                parsed = urlparse(normalized_source)
                filename = parsed.path.rsplit("/", 1)[-1] or "image"
                content_type = img_resp.headers.get("content-type", "").split(";", 1)[0]
                guessed_content_type = content_type or mimetypes.guess_type(filename)[0] or "image/jpeg"
                # If filename has no extension (e.g. "download"), add one based on content type
                if not Path(filename).suffix:
                    ext = mimetypes.guess_extension(guessed_content_type) or '.png'
                    filename = f'{filename}{ext}'
                return img_resp.content, filename, guessed_content_type

        if normalized_source.startswith("data:"):
            header, _, encoded = normalized_source.partition(",")
            if not encoded:
                raise ValueError("Invalid data URL image source")
            mime_type = header.split(";", 1)[0].removeprefix("data:") or "image/png"
            extension = mimetypes.guess_extension(mime_type) or ".png"
            image_bytes = HunyuanImageService.base64_to_bytes(encoded)
            return image_bytes, f"inline{extension}", mime_type

        image_bytes = HunyuanImageService.base64_to_bytes(normalized_source)
        return image_bytes, "image.jpg", "image/jpeg"

    async def _rewrite_wechat_body_images(
        self,
        account: Account,
        access_token: str,
        html_content: str,
        article_id: int,
    ) -> str:
        """Upload localized HTML images to WeChat and replace their src URLs."""
        if not html_content:
            return html_content

        article = await self.session.get(Article, article_id)
        if not article:
            raise ValueError(f'Article {article_id} not found')

        img_pattern = re.compile(
            r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'][^>]*>)',
            flags=re.IGNORECASE,
        )
        image_cache: dict[str, str] = {}

        async def replace_match(match: re.Match[str]) -> str:
            prefix = match.group(1)
            original_src = match.group(2).strip()
            suffix = match.group(3)

            if not original_src or self._is_wechat_image_url(original_src):
                return match.group(0)

            if original_src in image_cache:
                return f'{prefix}{image_cache[original_src]}{suffix}'

            try:
                media_asset = await self._get_or_create_body_media_asset(article, original_src)
                wechat_url = await self._upload_article_body_image_for_account(
                    account=account,
                    access_token=access_token,
                    media_asset=media_asset,
                )
                image_cache[original_src] = wechat_url
                logger.info(
                    'Article %d body image uploaded to WeChat for account %d: %s -> %s',
                    article_id,
                    account.id,
                    original_src,
                    wechat_url,
                )
                return f'{prefix}{wechat_url}{suffix}'
            except Exception as exc:
                logger.warning(
                    'Article %d body image upload failed for account %d source %s: %s',
                    article_id,
                    account.id,
                    original_src,
                    exc,
                )
                raise RuntimeError(
                    f'Body image upload failed for account {account.id}: {original_src}'
                ) from exc

        rewritten_parts: list[str] = []
        last_end = 0
        for match in img_pattern.finditer(html_content):
            rewritten_parts.append(html_content[last_end:match.start()])
            rewritten_parts.append(await replace_match(match))
            last_end = match.end()
        rewritten_parts.append(html_content[last_end:])

        return ''.join(rewritten_parts)

    @staticmethod
    def _markdown_to_html(
        markdown_text: str,
        theme: str = 'default',
    ) -> str:
        """Convert Markdown to styled HTML using wenyan-md CLI.

        Uses `wenyan render` from @wenyan-md/cli for beautiful WeChat-ready
        formatting with inline styles.  Falls back to a basic regex converter
        if wenyan is not installed.

        Args:
            markdown_text: Raw Markdown content.
            theme: Wenyan theme id (default, orangeheart, rainbow, etc.).
        """
        import shutil
        import subprocess
        import tempfile

        wenyan_bin = shutil.which('wenyan')
        if wenyan_bin:
            try:
                # Write markdown to a temp file so wenyan can read it
                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.md', delete=False, encoding='utf-8'
                ) as tmp:
                    tmp.write(markdown_text)
                    tmp_path = tmp.name

                result = subprocess.run(
                    [wenyan_bin, 'render', '-f', tmp_path, '-t', theme],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                import os
                os.unlink(tmp_path)

                if result.returncode == 0 and result.stdout.strip():
                    logger.info('Markdown rendered with wenyan (theme=%s)', theme)
                    from agent_publisher.services.wechat_style_service import (
                        WeChatStyleService,
                    )
                    return WeChatStyleService.inject_styles(result.stdout.strip())
                logger.warning(
                    'wenyan render failed (rc=%d): %s',
                    result.returncode,
                    result.stderr[:200],
                )
            except Exception as e:
                logger.warning('wenyan render error: %s, falling back to basic converter', e)
        else:
            logger.info('wenyan not found, using basic Markdown converter')

        # Fallback: basic regex-based Markdown to HTML
        return ArticleService._basic_markdown_to_html(markdown_text)

    @staticmethod
    def _basic_markdown_to_html(markdown_text: str) -> str:
        """Fallback basic Markdown to HTML conversion with WeChat inline styles."""
        import re

        from agent_publisher.services.wechat_style_service import WeChatStyleService

        html = markdown_text

        # Headers
        for i in range(6, 0, -1):
            pattern = r'^' + '#' * i + r'\s+(.+)$'
            replacement = f'<h{i}>\\1</h{i}>'
            html = re.sub(pattern, replacement, html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        # Links
        html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
        # Line breaks
        html = html.replace('\n\n', '</p><p>')
        html = f'<p>{html}</p>'

        # Apply WeChat-compatible inline styles
        html = WeChatStyleService.inject_styles(html)

        return html

    async def update_article(self, article_id: int, updates: dict) -> Article:
        """Update local article fields.

        Supported keys: title, digest, content, html_content, cover_image_url.
        When 'content' (Markdown) is modified, html_content is automatically
        re-rendered via wenyan.
        """
        article = await self.session.get(Article, article_id)
        if not article:
            raise ValueError(f'Article {article_id} not found')

        allowed_fields = {'title', 'digest', 'content', 'html_content', 'cover_image_url'}
        updated_fields: list[str] = []

        for key, value in updates.items():
            if key not in allowed_fields:
                continue
            if value is None:
                continue
            setattr(article, key, value)
            updated_fields.append(key)

        # Auto re-render html when markdown content changes,
        # but NOT when html_content was also explicitly provided (user's HTML wins).
        if 'content' in updated_fields and 'html_content' not in updated_fields:
            article.html_content = self._markdown_to_html(article.content)
            updated_fields.append('html_content')

        await self._sync_article_body_media_assets(article)

        await self.session.commit()
        await self.session.refresh(article)

        logger.info(
            'Article %d updated, fields=%s', article.id, updated_fields
        )
        return article

    async def sync_article_to_draft(
        self,
        article_id: int,
        operator: str = 'admin',
        target_account_ids: list[int] | None = None,
    ) -> ArticleSyncResponse:
        """Sync local article edits to WeChat draft boxes."""
        article, agent = await self._get_article_and_agent(article_id)
        accounts = await self._resolve_target_accounts(agent, target_account_ids)
        publish_html = await self._get_publish_html(article)

        results: list[AccountScopedPublishResult] = []
        synced_any = False

        for account in accounts:
            relation = await self._get_or_create_relation(article.id, account.id)
            media_id = relation.wechat_media_id or ''
            if not media_id:
                if account.id == agent.account_id and article.wechat_media_id:
                    media_id = article.wechat_media_id
                    relation.wechat_media_id = media_id
                else:
                    relation.sync_status = 'skipped'
                    relation.last_error = 'Draft media_id not found for this account'
                    results.append(
                        AccountScopedPublishResult(
                            account_id=account.id,
                            account_name=account.name,
                            status='skipped',
                            wechat_media_id='',
                            stage='sync',
                            error=relation.last_error,
                        )
                    )
                    continue

            relation.sync_status = 'processing'
            relation.last_error = ''
            await self.session.flush()

            try:
                access_token = await self._ensure_account_access_token(account)
                thumb_media_id = await self._upload_cover_thumb(article, access_token)
                scoped_html = await self._rewrite_wechat_body_images(
                    account=account,
                    access_token=access_token,
                    html_content=publish_html,
                    article_id=article.id,
                )
                draft_article = self._build_wechat_draft_article(
                    article=article,
                    agent=agent,
                    html_content=scoped_html,
                    thumb_media_id=thumb_media_id,
                )
                await WeChatService.update_draft(
                    access_token=access_token,
                    media_id=media_id,
                    articles=draft_article,
                    index=0,
                )

                relation.sync_status = 'synced'
                relation.last_error = ''
                relation.last_synced_at = datetime.now(timezone.utc)

                record = self._build_publish_record(
                    article_id=article.id,
                    account_id=account.id,
                    action='sync',
                    wechat_media_id=media_id,
                    status='success',
                    operator=operator,
                )
                self.session.add(record)

                results.append(
                    AccountScopedPublishResult(
                        account_id=account.id,
                        account_name=account.name,
                        status='success',
                        wechat_media_id=media_id,
                        stage='sync',
                        error='',
                    )
                )
                synced_any = True
            except Exception as exc:
                logger.error(
                    'Article %d sync failed for account %d: %s',
                    article.id,
                    account.id,
                    exc,
                )
                relation.sync_status = 'failed'
                relation.last_error = str(exc)

                record = self._build_publish_record(
                    article_id=article.id,
                    account_id=account.id,
                    action='sync',
                    wechat_media_id=media_id,
                    status='failed',
                    operator=operator,
                    error_message=str(exc),
                )
                self.session.add(record)

                results.append(
                    AccountScopedPublishResult(
                        account_id=account.id,
                        account_name=account.name,
                        status='failed',
                        wechat_media_id=media_id,
                        stage='sync',
                        error=str(exc),
                    )
                )

        await self.session.commit()
        await self.session.refresh(article)

        overall_status = self._aggregate_result_status(results)
        sync_status = 'synced' if synced_any else 'skipped'
        logger.info(
            'Article %d sync finished: overall_status=%s targets=%s',
            article.id,
            overall_status,
            [account.id for account in accounts],
        )
        return ArticleSyncResponse(
            ok=synced_any,
            article_id=article.id,
            overall_status=overall_status,
            sync_status=sync_status,
            target_account_ids=[account.id for account in accounts],
            results=results,
        )

    async def generate_variant(
        self,
        source_article_id: int,
        target_agent_id: int,
        style_id: str,
        step_callback: Callable[..., Awaitable[None]] | None = None,
    ) -> Article:
        """Generate a variant article from a source article using a style preset.

        Args:
            source_article_id: ID of the source article to rewrite.
            target_agent_id: Agent (and its account) the variant belongs to.
            style_id: Style preset identifier to use for rewriting.
            step_callback: Optional async callback for progress reporting.
        """
        from agent_publisher.config import settings
        from agent_publisher.models.style_preset import StylePreset
        from agent_publisher.services.style_preset_service import StylePresetService

        # 1. Load source article
        source = await self.session.get(Article, source_article_id)
        if not source:
            raise ValueError(f"Source article {source_article_id} not found")

        # 2. Load target agent
        agent = await self.session.get(Agent, target_agent_id)
        if not agent:
            raise ValueError(f"Target agent {target_agent_id} not found")

        # 3. Load style preset
        sps = StylePresetService(self.session)
        preset = await sps.get_preset(style_id)
        if not preset:
            raise ValueError(f"Style preset '{style_id}' not found")

        if step_callback:
            await step_callback("load_resources", "success", {
                "source_article_id": source.id,
                "source_title": source.title,
                "target_agent_id": agent.id,
                "style_id": style_id,
                "style_name": preset.name,
            })

        # 4. Build prompt from template — truncate content to 3000 chars
        source_content = source.content or ""
        if len(source_content) > 3000:
            source_content = source_content[:3000] + "\n\n[...内容已截断...]"

        prompt_text = preset.prompt.format(
            title=source.title or "",
            digest=source.digest or "",
            content=source_content,
        )

        messages = [
            {"role": "system", "content": "你是一位专业的内容改写编辑，擅长用不同风格改写文章。"},
            {"role": "user", "content": prompt_text},
        ]

        # 5. Call LLM with platform-level config
        provider = settings.default_llm_provider
        model = settings.default_llm_model
        api_key = settings.default_llm_api_key
        base_url = settings.default_llm_base_url

        raw_response = await self.llm.generate(
            provider=provider,
            model=model,
            api_key=api_key,
            messages=messages,
            base_url=base_url,
        )

        if step_callback:
            await step_callback("llm_generate", "success", {
                "response_length": len(raw_response),
                "provider": provider,
                "model": model,
            })

        # 6. Parse LLM response
        parsed = self.llm.parse_article_response(raw_response)

        # 7. Render Markdown to HTML
        html_content = self._markdown_to_html(parsed["content"])

        # 7b. If the source article has custom html_content with inline styles,
        # prefer it as the base: extract images from source html and inject into
        # variant html so body images are preserved.
        source_html = source.html_content or ""
        if source_html:
            # Extract all <img src="..."> from source html
            img_pattern = re.compile(
                r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']',
                flags=re.IGNORECASE,
            )
            source_imgs = img_pattern.findall(source_html)
            variant_img_count = len(img_pattern.findall(html_content))
            # If source has images but variant html has none, append them at end
            if source_imgs and variant_img_count == 0:
                img_tags = "".join(
                    f'<img src="{src}" style="max-width:100%;border-radius:8px;margin:16px 0;display:block;" />'
                    for src in source_imgs
                )
                html_content = html_content + img_tags
                logger.info(
                    "Variant %s: injected %d images from source article %d",
                    parsed["title"][:30], len(source_imgs), source_article_id,
                )

        # 8. Create variant article
        variant = Article(
            agent_id=target_agent_id,
            title=parsed["title"],
            digest=parsed["digest"],
            content=parsed["content"],
            html_content=html_content,
            cover_image_url=source.cover_image_url or "",
            images=[],
            source_news=source.source_news or [],
            status="draft",
            source_article_id=source_article_id,
            variant_style=style_id,
        )
        self.session.add(variant)
        await self.session.commit()
        await self.session.refresh(variant)

        if step_callback:
            await step_callback("save_variant", "success", {
                "article_id": variant.id,
                "title": variant.title,
                "style": style_id,
            })

        logger.info(
            "Variant generated: id=%d source=%d style=%s agent=%d",
            variant.id, source_article_id, style_id, target_agent_id,
        )
        return variant

    async def _get_article_and_agent(self, article_id: int) -> tuple[Article, Agent]:
        article = await self.session.get(Article, article_id)
        if not article:
            raise ValueError(f'Article {article_id} not found')

        agent = await self.session.get(Agent, article.agent_id)
        if not agent:
            raise ValueError(f'Agent {article.agent_id} not found')

        return article, agent

    async def _resolve_target_accounts(
        self,
        agent: Agent,
        target_account_ids: list[int] | None,
    ) -> list[Account]:
        resolved_ids = target_account_ids or [agent.account_id]
        unique_ids: list[int] = []
        for account_id in resolved_ids:
            if account_id not in unique_ids:
                unique_ids.append(account_id)

        accounts: list[Account] = []
        for account_id in unique_ids:
            account = await self.session.get(Account, account_id)
            if not account:
                raise ValueError(f'Account {account_id} not found')
            accounts.append(account)

        if not accounts:
            raise ValueError('No target accounts resolved for publishing')
        return accounts

    async def _ensure_account_access_token(self, account: Account) -> str:
        now = datetime.now(timezone.utc)
        token_expired = (
            not account.access_token
            or not account.token_expires_at
            or account.token_expires_at.replace(tzinfo=timezone.utc) < now
        )
        if token_expired:
            token, expires_at = await WeChatService.get_access_token(
                account.appid,
                account.appsecret,
            )
            account.access_token = token
            account.token_expires_at = expires_at
            await self.session.flush()
        return account.access_token or ''

    async def _upload_cover_thumb(self, article: Article, access_token: str) -> str:
        image_source = article.cover_image_url

        # Fallback: use the first body image when no explicit cover is set
        if not image_source:
            html_content = article.html_content or ''
            img_match = re.search(
                r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']',
                html_content,
                flags=re.IGNORECASE,
            )
            if img_match:
                image_source = img_match.group(1).strip()
                logger.info(
                    'Article %d has no cover, using first body image as thumb: %s',
                    article.id,
                    image_source[:100],
                )

        if not image_source:
            logger.warning('Article %d has no cover and no body images for thumb', article.id)
            return ''

        try:
            image_bytes, filename, _ = await self._load_image_resource(image_source)
            # Ensure filename has an extension for WeChat validation
            if not Path(filename).suffix:
                filename = f'{filename}.png'
            return await WeChatService.upload_thumb(
                access_token,
                image_bytes,
                filename=filename,
            )
        except Exception as exc:
            logger.error('Failed to upload cover image for article %d: %s', article.id, exc)
            return ''

    async def _get_publish_html(self, article: Article) -> str:
        from agent_publisher.services.wechat_style_service import WeChatStyleService

        publish_html = article.html_content

        # Only fall back to wenyan re-render when:
        # 1. There is no html_content at all, AND
        # 2. There is markdown content to render from
        if not publish_html and article.content:
            logger.info(
                'Article %d has no html_content, rendering markdown',
                article.id,
            )
            rendered = self._markdown_to_html(article.content)
            publish_html = rendered
            article.html_content = rendered
            await self.session.flush()
        elif publish_html:
            # Safety net: inject WeChat inline styles into any existing html_content
            # that may lack proper styling (e.g. uploaded HTML without inline styles).
            # Tags that already have style attributes are preserved as-is.
            publish_html = WeChatStyleService.inject_styles(publish_html)
            article.html_content = publish_html
            await self.session.flush()

        return publish_html

    async def _get_or_create_relation(
        self,
        article_id: int,
        account_id: int,
    ) -> ArticlePublishRelation:
        stmt = select(ArticlePublishRelation).where(
            ArticlePublishRelation.article_id == article_id,
            ArticlePublishRelation.account_id == account_id,
        )
        result = await self.session.execute(stmt)
        relation = result.scalar_one_or_none()
        if relation:
            return relation

        relation = ArticlePublishRelation(
            article_id=article_id,
            account_id=account_id,
            wechat_media_id='',
            publish_status='pending',
            sync_status='pending',
            last_error='',
        )
        self.session.add(relation)
        await self.session.flush()
        return relation

    def _build_wechat_draft_article(
        self,
        article: Article,
        agent: Agent,
        html_content: str,
        thumb_media_id: str,
    ) -> dict:
        author_name = agent.name
        if len(author_name) > 8:
            author_name = author_name[:8]

        draft_article: dict[str, str] = {
            'title': article.title,
            'author': author_name,
            'digest': article.digest,
            'content': html_content,
            'content_source_url': '',
        }
        if thumb_media_id:
            draft_article['thumb_media_id'] = thumb_media_id
        return draft_article

    def _build_publish_record(
        self,
        article_id: int,
        account_id: int,
        action: str,
        wechat_media_id: str,
        status: str,
        operator: str,
        error_message: str = '',
    ) -> PublishRecord:
        return PublishRecord(
            article_id=article_id,
            account_id=account_id,
            action=action,
            wechat_media_id=wechat_media_id,
            status=status,
            operator=operator,
            error_message=error_message,
        )

    @staticmethod
    def _aggregate_result_status(results: list[AccountScopedPublishResult]) -> str:
        if not results:
            return 'skipped'

        success_count = sum(1 for item in results if item.status == 'success')
        failed_count = sum(1 for item in results if item.status == 'failed')
        skipped_count = sum(1 for item in results if item.status == 'skipped')

        if success_count == len(results):
            return 'success'
        if failed_count == len(results):
            return 'failed'
        if skipped_count == len(results):
            return 'skipped'
        return 'partial'

    @staticmethod
    def _extract_media_id_from_download_url(image_source: str) -> int | None:
        normalized_source = (image_source or '').strip()
        # Support both relative (/api/media/13/download) and absolute URLs
        # (http://host:port/api/media/13/download)
        if '/api/media/' in normalized_source and normalized_source.endswith('/download'):
            try:
                return int(normalized_source.split('/api/media/')[1].split('/download')[0])
            except (ValueError, IndexError):
                pass
        return None

    @staticmethod
    def _is_wechat_image_url(image_source: str) -> bool:
        normalized_source = (image_source or '').strip().lower()
        return normalized_source.startswith('wx_fmt=') or 'mmbiz.qpic.cn' in normalized_source

    @staticmethod
    def _build_article_body_source_key(image_source: str) -> str:
        normalized_source = (image_source or '').strip()
        is_inline_source = normalized_source.startswith('data:') or (
            not normalized_source.startswith('http://')
            and not normalized_source.startswith('https://')
            and not normalized_source.startswith('/api/media/')
            and len(normalized_source) > 128
        )
        if is_inline_source:
            digest = hashlib.sha256(normalized_source.encode('utf-8')).hexdigest()
            return f'inline:{digest}'
        return normalized_source[:1000]

    async def _resolve_article_owner_email(self, article: Article) -> str:
        agent = await self.session.get(Agent, article.agent_id)
        if not agent:
            return ''

        account = await self.session.get(Account, agent.account_id)
        if not account:
            return ''
        return account.owner_email or ''

    async def _get_or_create_body_media_asset(
        self,
        article: Article,
        image_source: str,
    ) -> MediaAsset:
        media_id = self._extract_media_id_from_download_url(image_source)
        if media_id is not None:
            media_asset = await self.session.get(MediaAsset, media_id)
            if not media_asset:
                raise ValueError(f'Media asset {media_id} not found')
            return media_asset

        source_key = self._build_article_body_source_key(image_source)
        stmt = select(MediaAsset).where(
            MediaAsset.article_id == article.id,
            MediaAsset.source_kind == 'article_body',
            MediaAsset.source_url == source_key,
        )
        result = await self.session.execute(stmt)
        existing_asset = result.scalar_one_or_none()
        if existing_asset:
            return existing_asset

        image_bytes, filename, content_type = await self._load_image_resource(image_source)

        from agent_publisher.api.media import UPLOAD_DIR, _ensure_upload_dir

        _ensure_upload_dir()
        extension = Path(filename).suffix or mimetypes.guess_extension(content_type) or '.png'
        stored_filename = f'{uuid.uuid4().hex}{extension}'
        (UPLOAD_DIR / stored_filename).write_bytes(image_bytes)

        media_asset = MediaAsset(
            filename=filename,
            stored_filename=stored_filename,
            content_type=content_type,
            file_size=len(image_bytes),
            tags=['article_body'],
            description=f'Article {article.id} body image',
            owner_email=await self._resolve_article_owner_email(article),
            source_kind='article_body',
            source_url=source_key,
            article_id=article.id,
        )
        self.session.add(media_asset)
        await self.session.flush()
        return media_asset

    async def _sync_article_body_media_assets(self, article: Article) -> bool:
        html_content = article.html_content or ''
        if not html_content:
            return False

        img_pattern = re.compile(
            r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'][^>]*>)',
            flags=re.IGNORECASE,
        )
        rewritten_parts: list[str] = []
        last_end = 0
        changed = False

        for match in img_pattern.finditer(html_content):
            rewritten_parts.append(html_content[last_end:match.start()])
            prefix = match.group(1)
            original_src = match.group(2).strip()
            suffix = match.group(3)

            replacement = match.group(0)
            if original_src and not self._is_wechat_image_url(original_src):
                try:
                    media_asset = await self._get_or_create_body_media_asset(article, original_src)
                    localized_src = f'/api/media/{media_asset.id}/download'
                    replacement = f'{prefix}{localized_src}{suffix}'
                    changed = changed or localized_src != original_src
                except Exception as exc:
                    logger.warning(
                        'Article %d body image localization failed for %s: %s',
                        article.id,
                        original_src,
                        exc,
                    )

            rewritten_parts.append(replacement)
            last_end = match.end()

        rewritten_parts.append(html_content[last_end:])
        localized_html = ''.join(rewritten_parts)
        if localized_html != html_content:
            article.html_content = localized_html
            await self.session.flush()
            return True
        return changed

    async def _get_or_create_wechat_media_mapping(
        self,
        media_asset_id: int,
        account_id: int,
    ) -> MediaAssetWechatMapping:
        stmt = select(MediaAssetWechatMapping).where(
            MediaAssetWechatMapping.media_asset_id == media_asset_id,
            MediaAssetWechatMapping.account_id == account_id,
        )
        result = await self.session.execute(stmt)
        mapping = result.scalar_one_or_none()
        if mapping:
            return mapping

        mapping = MediaAssetWechatMapping(
            media_asset_id=media_asset_id,
            account_id=account_id,
            wechat_url='',
            upload_status='pending',
            error_message='',
        )
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def _upload_article_body_image_for_account(
        self,
        account: Account,
        access_token: str,
        media_asset: MediaAsset,
    ) -> str:
        mapping = await self._get_or_create_wechat_media_mapping(media_asset.id, account.id)
        if mapping.upload_status == 'success' and mapping.wechat_url:
            return mapping.wechat_url

        from agent_publisher.api.media import UPLOAD_DIR

        local_path = UPLOAD_DIR / media_asset.stored_filename
        if not local_path.is_file():
            raise FileNotFoundError(f'Media file not found on disk: {local_path}')

        mapping.upload_status = 'processing'
        mapping.error_message = ''
        await self.session.flush()

        try:
            # Ensure filename has a proper extension for WeChat validation
            upload_filename = media_asset.filename
            if not Path(upload_filename).suffix:
                ext = mimetypes.guess_extension(media_asset.content_type or '') or '.png'
                upload_filename = f'{upload_filename}{ext}'
            wechat_url = await WeChatService.upload_article_image(
                access_token=access_token,
                image_data=local_path.read_bytes(),
                filename=upload_filename,
                content_type=media_asset.content_type or 'image/jpeg',
            )
            mapping.wechat_url = wechat_url
            mapping.upload_status = 'success'
            mapping.error_message = ''
            mapping.uploaded_at = datetime.now(timezone.utc)
            await self.session.flush()
            return wechat_url
        except Exception as exc:
            mapping.upload_status = 'failed'
            mapping.error_message = str(exc)
            await self.session.flush()
            raise

    # ------------------------------------------------------------------
    # AI Beautify: LLM-powered HTML formatting for WeChat
    # ------------------------------------------------------------------

    async def ai_beautify_html(self, article: Article, style_hint: str = "") -> str:
        """Use LLM to beautify article HTML for WeChat Official Account layout.

        Sends the current html_content (or renders markdown first) to the LLM
        with formatting instructions. Returns the beautified HTML string and
        persists it on the article row.
        """
        from agent_publisher.config import settings

        html_input = article.html_content or ''
        if not html_input and article.content:
            html_input = self._markdown_to_html(article.content)

        if not html_input:
            raise ValueError("文章没有可美化的内容")

        system_prompt = (
            "你是一位顶级微信公众号排版设计师，你的排版作品在朋友圈被疯狂转发。\n"
            "你的任务是将用户提供的 HTML 内容进行专业级排版美化。\n\n"
            "## 核心原则\n"
            "- 所有样式必须用 inline style（微信编辑器不支持 <style> / <link>）\n"
            "- 不能使用 class / id 选择器\n"
            "- 保持原文内容完整，只优化排版样式\n"
            "- 只输出 HTML，不要解释文字\n\n"
            "## 排版设计规范（参考顶级公众号如「虎嗅」「36氪」「少数派」）\n\n"
            "### 整体容器\n"
            "- 外层 <section>，字体 -apple-system, 'PingFang SC', sans-serif\n"
            "- 正文 font-size: 16px, line-height: 1.75, color: #3f3f3f\n"
            "- padding: 10px 8px\n\n"
            "### 标题层级\n"
            "- h1（文章标题）: 24px, bold, #1a1a1a, 居中, margin: 30px 0 12px\n"
            "- h2（章节标题）: 用设计感的标题样式，例如：\n"
            "  左侧 4px 粗色条(#07C160) + padding-left:14px + 18px bold #222\n"
            "  或者：底部渐变色下划线 + 居中显示\n"
            "  或者：带圆角的浅色背景色块 + 左对齐\n"
            "  每篇文章保持同一种 h2 风格\n"
            "- h3: 16px, bold, #333, 左侧小圆点装饰\n\n"
            "### 段落与文字\n"
            "- <p>: margin: 0 0 20px 0, text-align: justify\n"
            "- <strong> 高亮关键句: color: #07C160 或 #2563eb\n"
            "- 首段或核心段可以用大字号(17px)强调\n\n"
            "### 引用块 (blockquote)\n"
            "- 圆角卡片风格: background: #f7f8fa, border-radius: 8px\n"
            "- 左边 4px 色条 #07C160\n"
            "- padding: 16px 20px, color: #555, font-size: 15px\n"
            "- 或者用浅绿色背景 #f0fdf4 + 深绿色文字\n\n"
            "### 列表\n"
            "- ul/ol 内 li: margin: 8px 0, padding-left: 8px\n"
            "- 可用 emoji 或色块替代默认圆点\n\n"
            "### 分隔线\n"
            "- 不要用默认 <hr>，用装饰性分隔: 三个居中小圆点(···)\n"
            "  或渐变细线: height:1px background:linear-gradient(to right, transparent, #ddd, transparent)\n\n"
            "### 数据/对比/卡片\n"
            "- 关键数据可以用卡片式排版: 浅色背景 + 大数字 + 小标签\n"
            "- 对比信息用两栏或色块区分\n\n"
            "### 尾部\n"
            "- 结尾段用不同颜色或斜体做 visual break\n"
            "- 最后的免责/注释用小字 13px, color: #999\n\n"
            "## 配色方案（选一套保持统一）\n"
            "- 方案A（微信绿）: 主色 #07C160, 辅色 #f0fdf4, 标题 #1a1a1a\n"
            "- 方案B（科技蓝）: 主色 #2563eb, 辅色 #eff6ff, 标题 #1e293b\n"
            "- 方案C（商务灰）: 主色 #374151, 辅色 #f3f4f6, 标题 #111827\n"
            "根据文章主题自动选择最匹配的配色。"
        )

        user_content = f"请美化以下 HTML 排版：\n\n{html_input}"
        if style_hint and style_hint.strip():
            user_content += f"\n\n用户额外要求：{style_hint.strip()}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        provider = settings.default_llm_provider
        model = settings.default_llm_model
        api_key = settings.default_llm_api_key
        base_url = settings.default_llm_base_url

        beautified = await self.llm.generate(
            provider=provider,
            model=model,
            api_key=api_key,
            messages=messages,
            base_url=base_url,
        )

        # Strip potential markdown code fences from LLM output
        beautified = beautified.strip()
        if beautified.startswith("```html"):
            beautified = beautified[7:]
        if beautified.startswith("```"):
            beautified = beautified[3:]
        if beautified.endswith("```"):
            beautified = beautified[:-3]
        beautified = beautified.strip()

        article.html_content = beautified
        await self.session.commit()
        await self.session.refresh(article)

        return beautified
