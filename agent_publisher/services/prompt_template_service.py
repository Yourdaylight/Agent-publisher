from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)

BUILTIN_PROMPT_TEMPLATES: list[dict] = [
    {
        "name": "爆款二创",
        "category": "rewrite",
        "description": "围绕已有热点或文章做公众号二创改写。",
        "content": (
            "请基于以下素材进行公众号文章二创。\n\n"
            "标题：{title}\n摘要：{digest}\n素材：\n{content}\n\n"
            "要求：\n"
            "1. 保留核心信息，但重写表达方式；\n"
            "2. 开头更抓人；\n"
            "3. 输出标题、摘要和 Markdown 正文。\n"
            "请按 ---TITLE--- / ---DIGEST--- / ---CONTENT--- 输出。"
        ),
        "variables": ["title", "digest", "content"],
    },
    {
        "name": "热点总结",
        "category": "summary",
        "description": "把多条热点整合成一篇总结稿。",
        "content": (
            "请将以下热点内容整理成一篇结构清晰的公众号总结稿。\n\n"
            "主题：{topic}\n热点列表：\n{content}\n\n"
            "要求：提炼共同趋势、分点总结、最后给出观点。"
        ),
        "variables": ["topic", "content"],
    },
    {
        "name": "观点扩写",
        "category": "expand",
        "description": "适合把摘要或短内容扩写为完整文章。",
        "content": (
            "请围绕以下核心观点扩写成一篇适合公众号发布的文章。\n\n"
            "核心观点：{content}\n\n要求：逻辑完整、有案例、有总结。"
        ),
        "variables": ["content"],
    },
]


class PromptTemplateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def init_builtin_templates(self) -> None:
        for item in BUILTIN_PROMPT_TEMPLATES:
            result = await self.session.execute(
                select(PromptTemplate).where(
                    PromptTemplate.name == item["name"],
                    PromptTemplate.is_builtin.is_(True),
                )
            )
            if result.scalar_one_or_none() is None:
                self.session.add(
                    PromptTemplate(
                        name=item["name"],
                        category=item["category"],
                        description=item["description"],
                        content=item["content"],
                        variables=item["variables"],
                        is_builtin=True,
                    )
                )
        await self.session.commit()

    async def list_templates(
        self,
        owner_email: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> Sequence[PromptTemplate]:
        stmt = select(PromptTemplate)
        if owner_email:
            stmt = stmt.where(
                or_(PromptTemplate.owner_email == owner_email, PromptTemplate.is_builtin.is_(True))
            )
        if category:
            stmt = stmt.where(PromptTemplate.category == category)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    PromptTemplate.name.like(like),
                    PromptTemplate.description.like(like),
                    PromptTemplate.content.like(like),
                )
            )
        stmt = stmt.order_by(PromptTemplate.is_builtin.desc(), PromptTemplate.id.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_template(self, template_id: int) -> PromptTemplate | None:
        return await self.session.get(PromptTemplate, template_id)

    async def create_template(
        self,
        *,
        owner_email: str | None,
        name: str,
        category: str,
        description: str = "",
        content: str = "",
        variables: list[str] | None = None,
    ) -> PromptTemplate:
        template = PromptTemplate(
            owner_email=owner_email,
            name=name,
            category=category,
            description=description,
            content=content,
            variables=variables or [],
            is_builtin=False,
        )
        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def update_template(self, template: PromptTemplate, updates: dict) -> PromptTemplate:
        for key in {"name", "category", "description", "content", "variables"}:
            if key in updates:
                setattr(template, key, updates[key])
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def delete_template(self, template: PromptTemplate) -> None:
        await self.session.delete(template)
        await self.session.commit()

    async def increment_usage(self, template_id: int) -> None:
        template = await self.session.get(PromptTemplate, template_id)
        if not template:
            return
        template.usage_count += 1
        await self.session.commit()
