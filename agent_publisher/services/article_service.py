from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.services.image_service import HunyuanImageService
from agent_publisher.services.llm_service import LLMService
from agent_publisher.services.rss_service import RSSService
from agent_publisher.services.wechat_service import WeChatService

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
        """Full pipeline: RSS -> LLM -> Image -> Article.

        Args:
            agent: The agent to generate an article for.
            step_callback: Optional async callback invoked after each step.
                Signature: (step_name: str, status: str, output: dict) -> None
            chunk_callback: Optional async callback for streaming LLM chunks.
                Signature: (chunk: str) -> None
        """
        logger.info("Generating article for agent=%s topic=%s", agent.name, agent.topic)

        # 1. Fetch RSS news
        news_items = await self.rss.fetch_agent_feeds(agent.rss_sources or [])
        if not news_items:
            logger.warning("No news items found for agent %s", agent.name)

        news_text = "\n".join(
            f"- [{item.title}]({item.link})\n  {item.summary[:200]}"
            for item in news_items[:15]
        )

        if step_callback:
            await step_callback(
                "rss_fetch",
                "success",
                {
                    "count": len(news_items),
                    "titles": [item.title for item in news_items[:15]],
                },
            )

        # 2. Generate article via LLM (streaming when chunk_callback is provided)
        api_key = agent.llm_api_key or ""
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
                provider=agent.llm_provider,
                model=agent.llm_model,
                api_key=api_key,
                messages=messages,
                base_url=agent.llm_base_url or "",
            )
            async for chunk in stream:
                raw_response += chunk
                await chunk_callback(chunk)
        else:
            raw_response = await self.llm.generate(
                provider=agent.llm_provider,
                model=agent.llm_model,
                api_key=api_key,
                messages=messages,
                base_url=agent.llm_base_url or "",
            )

        parsed = self.llm.parse_article_response(raw_response)

        if step_callback:
            await step_callback(
                "llm_generate",
                "success",
                {
                    "title": parsed.get("title", ""),
                    "content_length": len(parsed.get("content", "")),
                    "provider": agent.llm_provider,
                    "model": agent.llm_model,
                },
            )

        # 3. Generate cover image
        cover_image_url = ""
        image_prompt = ""
        image_status = "skipped"
        try:
            image_prompt = (
                f"为公众号文章生成封面配图。主题：{parsed['title']}。"
                f"风格：{agent.image_style or '现代简约风格'}。"
                "要求：无文字，色彩鲜明，适合作为公众号封面。"
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
        source_news = [
            {"title": item.title, "link": item.link, "source": item.source_name}
            for item in news_items[:15]
        ]

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

        if step_callback:
            await step_callback(
                "save_article",
                "success",
                {"article_id": article.id, "title": article.title},
            )

        logger.info("Article created: id=%d title=%s", article.id, article.title)
        return article

    async def publish_article(self, article_id: int) -> str:
        """Publish an article to WeChat draft box."""
        article = await self.session.get(Article, article_id)
        if not article:
            raise ValueError(f"Article {article_id} not found")

        agent = await self.session.get(Agent, article.agent_id)
        if not agent:
            raise ValueError(f"Agent {article.agent_id} not found")

        account = await self.session.get(Account, agent.account_id)
        if not account:
            raise ValueError(f"Account {agent.account_id} not found")

        # Refresh token if needed
        now = datetime.now(timezone.utc)
        if not account.access_token or not account.token_expires_at or account.token_expires_at < now:
            token, expires_at = await WeChatService.get_access_token(
                account.appid, account.appsecret
            )
            account.access_token = token
            account.token_expires_at = expires_at
            await self.session.commit()

        # Upload cover image if available
        thumb_media_id = ""
        if article.cover_image_url:
            try:
                image_bytes = HunyuanImageService.base64_to_bytes(article.cover_image_url)
                thumb_media_id = await WeChatService.upload_thumb(
                    account.access_token, image_bytes
                )
            except Exception as e:
                logger.error("Failed to upload cover image: %s", e)

        # Push to draft
        draft_article = {
            "title": article.title,
            "author": agent.name,
            "digest": article.digest,
            "content": article.html_content,
            "thumb_media_id": thumb_media_id,
            "content_source_url": "",
        }
        media_id = await WeChatService.add_draft(account.access_token, [draft_article])

        article.wechat_media_id = media_id
        article.status = "published"
        article.published_at = now
        await self.session.commit()

        logger.info("Article %d published, media_id=%s", article.id, media_id)
        return media_id

    @staticmethod
    def _markdown_to_html(markdown_text: str) -> str:
        """Basic Markdown to HTML conversion for WeChat."""
        import re

        html = markdown_text

        # Headers
        for i in range(6, 0, -1):
            pattern = r"^" + "#" * i + r"\s+(.+)$"
            replacement = f"<h{i}>\\1</h{i}>"
            html = re.sub(pattern, replacement, html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        # Italic
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        # Links
        html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)
        # Line breaks
        html = html.replace("\n\n", "</p><p>")
        html = f"<p>{html}</p>"

        return html
