"""Initialize built-in Agent(s) on first startup.

Follows the same idempotent pattern used by ``StylePresetService.init_builtin_presets``.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.agent import Agent

logger = logging.getLogger(__name__)

BUILTIN_AGENT: dict = {
    "name": "锐评官",
    "topic": "科技与互联网",
    "description": (
        "你是一位犀利的科技评论家，擅长以独到视角解读互联网热点事件。"
        "你的文风辛辣但不失理性，善于透过现象看本质，用通俗易懂的语言"
        "向读者传递深度思考。你关注科技行业的商业逻辑、产品设计、"
        "用户体验以及技术趋势，经常引用行业数据和历史案例来佐证观点。"
    ),
    "prompt_template": (
        "你是「锐评官」——一位犀利、有态度的科技自媒体作者。\n\n"
        "写作要求：\n"
        "1. 标题要有观点、有冲击力，引发读者好奇\n"
        "2. 开头用一句话亮明态度，不要铺垫太久\n"
        "3. 正文结构清晰，每个段落围绕一个核心论点\n"
        "4. 善用数据、对比、类比来增强说服力\n"
        "5. 语气犀利但不刻薄，观点鲜明但留有余地\n"
        "6. 适当加入行业 insider 视角，体现专业度\n"
        "7. 结尾给出前瞻性判断或引发思考的问题\n"
        "8. 使用 Markdown 格式，善用小标题、引用、加粗\n"
        "9. 字数 1500-3000 字\n\n"
        "请按以下格式输出：\n"
        "---TITLE---\n新标题\n---DIGEST---\n新摘要\n---CONTENT---\nMarkdown正文"
    ),
    "image_style": "现代科技风格，简洁明快，色彩鲜明",
    "role": "full_pipeline",
    "source_mode": "rss",
}


async def init_builtin_agent(session: AsyncSession) -> None:
    """Ensure the built-in agent exists. Does NOT overwrite user edits."""
    result = await session.execute(
        select(Agent).where(Agent.is_builtin.is_(True))
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        logger.debug("Built-in agent already exists (id=%s), skipping.", existing.id)
        return

    agent = Agent(
        name=BUILTIN_AGENT["name"],
        topic=BUILTIN_AGENT["topic"],
        description=BUILTIN_AGENT["description"],
        prompt_template=BUILTIN_AGENT["prompt_template"],
        image_style=BUILTIN_AGENT["image_style"],
        role=BUILTIN_AGENT["role"],
        source_mode=BUILTIN_AGENT["source_mode"],
        account_id=None,
        is_builtin=True,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    logger.info("Created built-in agent '%s' (id=%s).", agent.name, agent.id)
