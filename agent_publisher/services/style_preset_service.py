"""Service for managing style presets (CRUD + built-in initialisation)."""
from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.style_preset import StylePreset

logger = logging.getLogger(__name__)

# Built-in style presets with full prompt templates.
# Placeholders: {title}, {content}, {digest}
BUILTIN_PRESETS: list[dict] = [
    {
        "style_id": "tech",
        "name": "科技风",
        "description": "偏向科技媒体的理性、数据驱动风格，强调前沿趋势和行业洞察",
        "prompt": (
            '你是一位资深科技媒体编辑。请将以下文章改写为科技风格的公众号文章。\n\n'
            '原始标题：{title}\n原始摘要：{digest}\n\n原始正文：\n{content}\n\n'
            '要求：\n'
            '1. 标题简洁有力，体现科技前沿感\n'
            '2. 使用数据和事实支撑观点\n'
            '3. 专业术语适当保留但附带简要解释\n'
            '4. 行文理性客观，避免过度情绪化\n'
            '5. 使用 Markdown 格式\n'
            '6. 字数 1500-3000 字\n\n'
            '请按以下格式输出：\n'
            '---TITLE---\n新标题\n---DIGEST---\n新摘要\n---CONTENT---\nMarkdown正文'
        ),
    },
    {
        "style_id": "uncle",
        "name": "大叔风",
        "description": "温暖、成熟、有阅历的叙述风格，像一位睿智长辈在分享经验",
        "prompt": (
            '你是一位阅历丰富、温暖睿智的大叔。请将以下文章改写为「大叔风」的公众号文章。\n\n'
            '原始标题：{title}\n原始摘要：{digest}\n\n原始正文：\n{content}\n\n'
            '要求：\n'
            '1. 标题亲切接地气，带有人生感悟\n'
            '2. 行文温暖从容，像跟朋友聊天\n'
            '3. 适当加入生活化比喻和个人体会\n'
            '4. 保持内容的深度和思考性\n'
            '5. 使用 Markdown 格式\n'
            '6. 字数 1500-3000 字\n\n'
            '请按以下格式输出：\n'
            '---TITLE---\n新标题\n---DIGEST---\n新摘要\n---CONTENT---\nMarkdown正文'
        ),
    },
    {
        "style_id": "clickbait",
        "name": "标题党",
        "description": "吸引眼球、制造悬念的风格，追求高点击率和传播力",
        "prompt": (
            '你是一位精通流量密码的自媒体运营高手。请将以下文章改写为「标题党」风格的公众号文章。\n\n'
            '原始标题：{title}\n原始摘要：{digest}\n\n原始正文：\n{content}\n\n'
            '要求：\n'
            '1. 标题极具吸引力，善用数字、悬念、反转等技巧\n'
            '2. 开头就抓人眼球，制造好奇心\n'
            '3. 适当运用情绪化表达和夸张修辞\n'
            '4. 分段密集，善用短句增强节奏感\n'
            '5. 注意：内容本身要有实质，不能纯标题党无干货\n'
            '6. 使用 Markdown 格式\n'
            '7. 字数 1500-3000 字\n\n'
            '请按以下格式输出：\n'
            '---TITLE---\n新标题\n---DIGEST---\n新摘要\n---CONTENT---\nMarkdown正文'
        ),
    },
    {
        "style_id": "literary",
        "name": "文艺风",
        "description": "优美细腻、注重文学表达和审美意境的写作风格",
        "prompt": (
            '你是一位文笔优美的专栏作家。请将以下文章改写为「文艺风」的公众号文章。\n\n'
            '原始标题：{title}\n原始摘要：{digest}\n\n原始正文：\n{content}\n\n'
            '要求：\n'
            '1. 标题富有诗意和文学美感\n'
            '2. 行文优美流畅，注重遣词造句\n'
            '3. 善用比喻、排比等修辞手法\n'
            '4. 情感细腻，有画面感和意境\n'
            '5. 保持内容信息量，不要空洞抒情\n'
            '6. 使用 Markdown 格式\n'
            '7. 字数 1500-3000 字\n\n'
            '请按以下格式输出：\n'
            '---TITLE---\n新标题\n---DIGEST---\n新摘要\n---CONTENT---\nMarkdown正文'
        ),
    },
    {
        "style_id": "casual",
        "name": "口语化",
        "description": "轻松随意、贴近日常口语的表达风格，像朋友间聊天",
        "prompt": (
            '你是一位说话轻松幽默的自媒体博主。请将以下文章改写为「口语化」的公众号文章。\n\n'
            '原始标题：{title}\n原始摘要：{digest}\n\n原始正文：\n{content}\n\n'
            '要求：\n'
            '1. 标题口语化、接地气，像朋友在对话\n'
            '2. 大量使用日常口语表达，避免书面语\n'
            '3. 适当加入网络流行语、emoji 和语气词\n'
            '4. 节奏轻快，段落短小，适合手机阅读\n'
            '5. 保持内容的信息量和观点\n'
            '6. 使用 Markdown 格式\n'
            '7. 字数 1500-3000 字\n\n'
            '请按以下格式输出：\n'
            '---TITLE---\n新标题\n---DIGEST---\n新摘要\n---CONTENT---\nMarkdown正文'
        ),
    },
    {
        "style_id": "professional",
        "name": "专业严谨",
        "description": "学术化、逻辑严密的专业风格，适合深度分析和行业报告",
        "prompt": (
            '你是一位严谨的行业分析师。请将以下文章改写为「专业严谨」风格的公众号文章。\n\n'
            '原始标题：{title}\n原始摘要：{digest}\n\n原始正文：\n{content}\n\n'
            '要求：\n'
            '1. 标题专业、准确，体现深度分析\n'
            '2. 行文逻辑严密，论证层次清晰\n'
            '3. 使用专业术语和规范表达\n'
            '4. 引用数据和事实作为论据\n'
            '5. 结论客观审慎，避免武断\n'
            '6. 使用 Markdown 格式，善用小标题分层\n'
            '7. 字数 1500-3000 字\n\n'
            '请按以下格式输出：\n'
            '---TITLE---\n新标题\n---DIGEST---\n新摘要\n---CONTENT---\nMarkdown正文'
        ),
    },
]


class StylePresetService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def init_builtin_presets(self) -> None:
        """Insert built-in presets if they do not already exist (upsert-safe).

        Existing presets (even built-in ones) are **not** overwritten so that
        user edits are preserved across restarts.
        """
        for preset_data in BUILTIN_PRESETS:
            existing = await self.session.execute(
                select(StylePreset).where(
                    StylePreset.style_id == preset_data["style_id"]
                )
            )
            if existing.scalar_one_or_none() is None:
                preset = StylePreset(
                    style_id=preset_data["style_id"],
                    name=preset_data["name"],
                    description=preset_data["description"],
                    prompt=preset_data["prompt"],
                    is_builtin=True,
                )
                self.session.add(preset)
                logger.info("Created built-in style preset: %s", preset_data["style_id"])

        await self.session.commit()
        logger.info("Built-in style presets initialised.")

    async def list_presets(self) -> Sequence[StylePreset]:
        """Return all presets ordered by id."""
        result = await self.session.execute(
            select(StylePreset).order_by(StylePreset.id)
        )
        return result.scalars().all()

    async def get_preset(self, style_id: str) -> StylePreset | None:
        """Fetch a single preset by its style_id."""
        result = await self.session.execute(
            select(StylePreset).where(StylePreset.style_id == style_id)
        )
        return result.scalar_one_or_none()

    async def create_preset(
        self,
        style_id: str,
        name: str,
        description: str = "",
        prompt: str = "",
    ) -> StylePreset:
        """Create a custom (non-builtin) style preset."""
        existing = await self.get_preset(style_id)
        if existing:
            raise ValueError(f"Style preset '{style_id}' already exists")

        preset = StylePreset(
            style_id=style_id,
            name=name,
            description=description,
            prompt=prompt,
            is_builtin=False,
        )
        self.session.add(preset)
        await self.session.commit()
        await self.session.refresh(preset)
        logger.info("Created custom style preset: %s", style_id)
        return preset

    async def update_preset(
        self,
        style_id: str,
        updates: dict,
    ) -> StylePreset:
        """Update an existing preset (both builtin and custom are editable)."""
        preset = await self.get_preset(style_id)
        if not preset:
            raise ValueError(f"Style preset '{style_id}' not found")

        allowed_fields = {"name", "description", "prompt"}
        for key, value in updates.items():
            if key in allowed_fields and value is not None:
                setattr(preset, key, value)

        await self.session.commit()
        await self.session.refresh(preset)
        logger.info("Updated style preset: %s", style_id)
        return preset

    async def delete_preset(self, style_id: str) -> None:
        """Delete a custom preset. Built-in presets cannot be deleted."""
        preset = await self.get_preset(style_id)
        if not preset:
            raise ValueError(f"Style preset '{style_id}' not found")
        if preset.is_builtin:
            raise PermissionError("Cannot delete built-in style preset")

        await self.session.delete(preset)
        await self.session.commit()
        logger.info("Deleted style preset: %s", style_id)
