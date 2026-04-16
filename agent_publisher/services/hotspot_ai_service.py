"""热点 AI 分析服务 — 复刻 TrendRadar AI 能力

利用已有 LLMService 实现:
  - AI 智能筛选 (兴趣标签提取 + 批量相关性评分)
  - AI 趋势分析 (结构化洞察输出)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.candidate_material import CandidateMaterial
from agent_publisher.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def _get_llm_config() -> dict:
    """获取平台级 LLM 配置"""
    from agent_publisher.config import settings

    return {
        "provider": settings.default_llm_provider,
        "model": settings.default_llm_model,
        "api_key": settings.default_llm_api_key,
        "base_url": settings.default_llm_base_url,
    }


class HotspotAIService:
    """热点 AI 分析 — 利用已有 LLMService 调用 LLM"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = LLMService()

    # ──────────────────────────────────────────────────────────────────
    # AI 智能筛选
    # ──────────────────────────────────────────────────────────────────

    async def extract_interest_tags(self, interests_description: str) -> list[dict]:
        """从兴趣描述中提取结构化标签

        Args:
            interests_description: 自然语言兴趣描述, 如 "关注AI技术、创业投资"

        Returns:
            [{"tag": "AI技术", "description": "人工智能相关技术动态"}, ...]
        """
        cfg = _get_llm_config()

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个内容标签分析师。根据用户描述的兴趣领域，提取结构化的兴趣标签。"
                    "每个标签包含 tag(简短标签名) 和 description(标签含义解释)。"
                    "输出 JSON 数组格式。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"请从以下兴趣描述中提取结构化标签:\n\n{interests_description}\n\n"
                    '输出格式: [{"tag": "标签名", "description": "标签含义"}]\n'
                    "直接输出 JSON，不要其他文字。"
                ),
            },
        ]

        try:
            resp = await self.llm.generate(
                provider=cfg["provider"],
                model=cfg["model"],
                api_key=cfg["api_key"],
                messages=messages,
                base_url=cfg["base_url"],
            )
            # Parse JSON from response
            resp_clean = resp.strip()
            if resp_clean.startswith("```"):
                # Strip markdown code block
                resp_clean = resp_clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            tags = json.loads(resp_clean)
            return tags if isinstance(tags, list) else []
        except Exception as e:
            logger.error("Failed to extract interest tags: %s", e)
            return []

    async def batch_classify_relevance(
        self,
        items: list[dict],
        tags: list[dict],
        interests: str,
        batch_size: int = 50,
    ) -> list[dict]:
        """批量评估新闻与兴趣的相关性

        Args:
            items: [{"index": 0, "title": "..."}, ...]
            tags: 兴趣标签列表
            interests: 兴趣描述原文
            batch_size: 每批处理数量

        Returns:
            [{"item_index": 0, "tag": "AI技术", "score": 0.85}, ...]
        """
        if not items or not tags:
            return []

        cfg = _get_llm_config()
        all_results: list[dict] = []

        # Process in batches
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            items_text = "\n".join(f"[{item['index']}] {item['title']}" for item in batch)
            tags_text = ", ".join(t["tag"] for t in tags)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一个内容相关性评估专家。评估每条新闻与用户兴趣标签的相关性。"
                        f"用户兴趣领域: {interests}\n"
                        f"兴趣标签: {tags_text}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请评估以下新闻与兴趣标签的相关性(0-1分):\n\n{items_text}\n\n"
                        '输出 JSON 数组: [{"item_index": 0, "tag": "最相关标签", "score": 0.85}]\n'
                        "只输出相关度 > 0.3 的结果。直接输出 JSON，不要其他文字。"
                    ),
                },
            ]

            try:
                resp = await self.llm.generate(
                    provider=cfg["provider"],
                    model=cfg["model"],
                    api_key=cfg["api_key"],
                    messages=messages,
                    base_url=cfg["base_url"],
                )
                resp_clean = resp.strip()
                if resp_clean.startswith("```"):
                    resp_clean = resp_clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                batch_results = json.loads(resp_clean)
                if isinstance(batch_results, list):
                    all_results.extend(batch_results)
            except Exception as e:
                logger.error("Failed to classify batch starting at %d: %s", start, e)

        return all_results

    async def ai_filter_materials(
        self,
        materials: list[CandidateMaterial],
        agent_topic: str,
    ) -> list[tuple[CandidateMaterial, float]]:
        """对素材进行 AI 相关性评分

        Args:
            materials: 待评分的素材列表
            agent_topic: Agent 的主题/领域描述

        Returns:
            [(material, score), ...] 按分数降序排列
        """
        if not materials:
            return []

        # Extract tags from agent topic
        tags = await self.extract_interest_tags(agent_topic)
        if not tags:
            # Fallback: use topic as single tag
            tags = [{"tag": agent_topic, "description": agent_topic}]

        # Prepare items for classification
        items = [
            {"index": i, "title": f"{m.title} - {m.summary[:100]}"} for i, m in enumerate(materials)
        ]

        # Classify
        results = await self.batch_classify_relevance(
            items=items,
            tags=tags,
            interests=agent_topic,
        )

        # Build score map
        score_map: dict[int, float] = {}
        for r in results:
            idx = r.get("item_index", -1)
            score = float(r.get("score", 0))
            if 0 <= idx < len(materials):
                # Keep highest score if multiple tags match
                score_map[idx] = max(score_map.get(idx, 0), score)

        # Build result list
        scored: list[tuple[CandidateMaterial, float]] = []
        for i, m in enumerate(materials):
            ai_score = score_map.get(i, 0.0)
            scored.append((m, ai_score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ──────────────────────────────────────────────────────────────────
    # AI 趋势分析
    # ──────────────────────────────────────────────────────────────────

    @dataclass
    class TrendAnalysisResult:
        """趋势分析结果"""

        core_trends: str = ""  # 核心热点与舆情
        sentiment: str = ""  # 舆论风向与争议
        signals: str = ""  # 异动与弱信号
        outlook: str = ""  # 研判与建议
        success: bool = False
        total_analyzed: int = 0

    async def analyze_trends(
        self,
        materials: list[CandidateMaterial],
        agent_topic: str = "",
    ) -> "HotspotAIService.TrendAnalysisResult":
        """对采集到的热点素材进行趋势分析

        Args:
            materials: 热点素材列表
            agent_topic: 可选的领域聚焦描述

        Returns:
            TrendAnalysisResult 结构化洞察
        """
        result = self.TrendAnalysisResult(total_analyzed=len(materials))

        if not materials:
            return result

        cfg = _get_llm_config()

        # Build news digest
        news_lines = []
        for i, m in enumerate(materials[:80], 1):  # Limit to 80 items
            score_info = f" [质量分:{m.quality_score:.2f}]" if m.quality_score else ""
            meta = m.extra_metadata or {}
            platform = meta.get("platform_name", m.source_identity)
            news_lines.append(f"{i}. [{platform}] {m.title}{score_info}")

        news_text = "\n".join(news_lines)
        topic_hint = f"\n领域聚焦: {agent_topic}" if agent_topic else ""

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一位资深的舆情分析师和趋势研究专家。"
                    "你需要从多个平台的热点新闻中提炼出深度洞察。"
                    "分析应具有前瞻性和实用性。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"以下是从多个平台采集的热点新闻列表：{topic_hint}\n\n"
                    f"{news_text}\n\n"
                    "请从以下四个维度进行深度分析：\n\n"
                    "## 1. 核心热点与舆情\n"
                    "识别最重要的3-5个核心话题，分析其热度来源和传播特征。\n\n"
                    "## 2. 舆论风向与争议\n"
                    "分析公众情绪倾向、争议焦点和观点分化。\n\n"
                    "## 3. 异动与弱信号\n"
                    "识别不寻常的趋势变化、新兴话题或值得关注的弱信号。\n\n"
                    "## 4. 研判与建议\n"
                    "对未来趋势走向做出判断，给出内容创作或关注建议。\n\n"
                    "请按上述结构输出分析结果，每个部分用 ## 标题分隔。"
                ),
            },
        ]

        try:
            resp = await self.llm.generate(
                provider=cfg["provider"],
                model=cfg["model"],
                api_key=cfg["api_key"],
                messages=messages,
                base_url=cfg["base_url"],
            )

            # Parse sections
            sections = _parse_trend_sections(resp)
            result.core_trends = sections.get("核心热点与舆情", sections.get("1", ""))
            result.sentiment = sections.get("舆论风向与争议", sections.get("2", ""))
            result.signals = sections.get("异动与弱信号", sections.get("3", ""))
            result.outlook = sections.get("研判与建议", sections.get("4", ""))
            result.success = True

        except Exception as e:
            logger.error("Failed to analyze trends: %s", e)

        return result


def _parse_trend_sections(text: str) -> dict[str, str]:
    """解析趋势分析 LLM 输出的各个段落"""
    import re

    sections: dict[str, str] = {}
    # Match ## N. Title or ## Title patterns
    parts = re.split(r"##\s*\d*\.?\s*", text)
    headers = re.findall(r"##\s*\d*\.?\s*(.+?)[\n\r]", text)

    for i, header in enumerate(headers):
        header_clean = header.strip().rstrip("：:")
        if i + 1 < len(parts):
            content = parts[i + 1].strip()
            sections[header_clean] = content
            # Also store by number
            sections[str(i + 1)] = content

    return sections
