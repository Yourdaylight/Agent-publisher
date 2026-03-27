"""热榜抓取服务 — 复刻 TrendRadar 核心能力

包含:
  A. 热榜抓取 (NewsNow API)
  B. 权重排名算法
  C. 关键词过滤
  D. 采集入库
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
from dataclasses import dataclass, field

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.schemas.candidate_material import CandidateMaterialCreate
from agent_publisher.schemas.source_config import TRENDING_PLATFORMS
from agent_publisher.services.candidate_material_service import CandidateMaterialService

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Part A: 热榜抓取
# ═══════════════════════════════════════════════════════════════════════

NEWSNOW_API = "https://newsnow.busiyi.world/api/s"

# Platform ID → display name lookup
_PLATFORM_NAME_MAP: dict[str, str] = {p["id"]: p["name"] for p in TRENDING_PLATFORMS}

# Browser-like headers required by NewsNow API
_NEWSNOW_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://newsnow.busiyi.world/",
}


@dataclass
class TrendingItem:
    """单条热榜条目"""
    title: str
    url: str
    mobile_url: str = ""
    platform_id: str = ""
    platform_name: str = ""
    rank: int = 0
    hot_value: str = ""


async def fetch_platform(
    platform_id: str,
    client: httpx.AsyncClient | None = None,
    timeout: float = 15.0,
) -> list[TrendingItem]:
    """抓取单个平台热榜 — 通过 NewsNow API"""
    platform_name = _PLATFORM_NAME_MAP.get(platform_id, platform_id)
    should_close = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout, headers=_NEWSNOW_HEADERS)

    try:
        resp = await client.get(NEWSNOW_API, params={"id": platform_id})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch trending for %s: %s", platform_id, e)
        return []
    finally:
        if should_close:
            await client.aclose()

    items: list[TrendingItem] = []
    entries = data.get("data", data.get("items", []))
    if isinstance(entries, dict):
        entries = entries.get("items", [])

    for idx, entry in enumerate(entries):
        if isinstance(entry, dict):
            items.append(TrendingItem(
                title=entry.get("title", "").strip(),
                url=entry.get("url", entry.get("link", "")),
                mobile_url=entry.get("mobileUrl", ""),
                platform_id=platform_id,
                platform_name=platform_name,
                rank=idx + 1,
                hot_value=str(entry.get("extra", {}).get("hotValue", ""))
                if isinstance(entry.get("extra"), dict) else "",
            ))

    logger.info("Fetched %d items from %s (%s)", len(items), platform_id, platform_name)
    return items


async def fetch_platforms_batch(
    platform_ids: list[str],
    concurrency: int = 3,
) -> dict[str, list[TrendingItem]]:
    """并发抓取多个平台热榜，Semaphore 限流"""
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, list[TrendingItem]] = {}

    async def _fetch_one(pid: str) -> None:
        async with sem:
            async with httpx.AsyncClient(timeout=15, headers=_NEWSNOW_HEADERS) as client:
                items = await fetch_platform(pid, client=client)
                results[pid] = items

    await asyncio.gather(*[_fetch_one(pid) for pid in platform_ids], return_exceptions=True)
    return results


# ═══════════════════════════════════════════════════════════════════════
# Part B: 权重排名算法
# ═══════════════════════════════════════════════════════════════════════

def calculate_trending_weight(
    rank: int,
    count: int = 1,
    ranks: list[int] | None = None,
) -> float:
    """计算热点权重

    权重公式: rank_weight × 0.4 + frequency_weight × 0.3 + hotness_weight × 0.3
      - rank_weight:      基于排名的分数 (排名越高分越高)
      - frequency_weight: 跨平台出现次数
      - hotness_weight:   基于最高排名的热度

    Args:
        rank: 该条目在某平台的排名 (1-based)
        count: 该条目跨平台出现次数
        ranks: 该条目在各平台的所有排名列表

    Returns:
        权重分数 (float, 通常 0~30+)
    """
    if ranks is None:
        ranks = [rank]

    # Rank weight: top items get higher scores (exponential decay)
    rank_weight = max(0, 50 * math.exp(-0.05 * (rank - 1)))

    # Frequency weight: cross-platform appearance
    frequency_weight = min(count * 10, 50)

    # Hotness weight: best rank across platforms
    best_rank = min(ranks) if ranks else rank
    hotness_weight = max(0, 50 * math.exp(-0.03 * (best_rank - 1)))

    return rank_weight * 0.4 + frequency_weight * 0.3 + hotness_weight * 0.3


def weight_to_quality_score(weight: float, k: float = 30.0) -> float:
    """Sigmoid 归一化: score = weight / (weight + k)

    将 weight 映射到 [0, 1) 区间.
    k 控制曲线形状: k 越大, 需要越高 weight 才能达到高分.

    Examples:
        weight=10 → ~0.25
        weight=30 → ~0.50
        weight=60 → ~0.67
    """
    if weight <= 0:
        return 0.0
    return weight / (weight + k)


# ═══════════════════════════════════════════════════════════════════════
# Part C: 关键词过滤
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class KeywordRule:
    """一条过滤规则

    规则格式:
      - 普通词: optional 匹配 (任一即可)
      - +前缀:  required 匹配 (必须全部包含)
      - !前缀:  exclude 排除 (命中则排除)
      - /pattern/: 正则匹配
    """
    required: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    patterns: list[re.Pattern] = field(default_factory=list)


def parse_keyword_rules(rules_text: str) -> list[KeywordRule]:
    """解析关键词规则配置文本

    每行一条规则, 关键词之间用空格或逗号分隔.
    前缀: + (必须包含), ! (排除), /.../ (正则)

    Example:
        "+AI 技术 !广告"
        "ChatGPT, GPT-4, /大模型/"
    """
    rules: list[KeywordRule] = []

    for line in rules_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        rule = KeywordRule()
        # Split by comma or whitespace
        tokens = re.split(r'[,，\s]+', line)

        for token in tokens:
            token = token.strip()
            if not token:
                continue

            if token.startswith("+"):
                word = token[1:].strip()
                if word:
                    rule.required.append(word)
            elif token.startswith("!"):
                word = token[1:].strip()
                if word:
                    rule.exclude.append(word)
            elif token.startswith("/") and token.endswith("/") and len(token) > 2:
                pattern_str = token[1:-1]
                try:
                    rule.patterns.append(re.compile(pattern_str, re.IGNORECASE))
                except re.error:
                    logger.warning("Invalid regex in keyword rule: %s", token)
            else:
                rule.optional.append(token)

        if rule.required or rule.optional or rule.patterns:
            rules.append(rule)

    return rules


def matches_any_rule(title: str, rules: list[KeywordRule]) -> bool:
    """检查标题是否匹配任一规则"""
    if not rules:
        return True  # 没有规则 = 全部通过

    title_lower = title.lower()

    for rule in rules:
        # Check exclude first
        if any(ex.lower() in title_lower for ex in rule.exclude):
            continue

        # Check required (all must match)
        if rule.required:
            if not all(req.lower() in title_lower for req in rule.required):
                continue

        # Check optional (any must match) or patterns
        has_optional = bool(rule.optional)
        has_patterns = bool(rule.patterns)

        optional_match = (
            not has_optional
            or any(opt.lower() in title_lower for opt in rule.optional)
        )
        pattern_match = (
            not has_patterns
            or any(p.search(title) for p in rule.patterns)
        )

        # If both optional and patterns are specified, either can match
        # If only one is specified, it must match
        # If neither is specified (only required), required check above suffices
        if has_optional and has_patterns:
            if optional_match or pattern_match:
                return True
        elif has_optional:
            if optional_match:
                return True
        elif has_patterns:
            if pattern_match:
                return True
        else:
            # Only required keywords (already checked above)
            if rule.required:
                return True

    return False


def filter_items(
    items: list[TrendingItem],
    rules: list[KeywordRule],
) -> list[TrendingItem]:
    """按规则过滤热榜条目"""
    if not rules:
        return items
    return [item for item in items if matches_any_rule(item.title, rules)]


# ═══════════════════════════════════════════════════════════════════════
# Part D: 采集入库
# ═══════════════════════════════════════════════════════════════════════

class TrendingCollectorService:
    """热榜采集器 — 抓取 → 过滤 → 评分 → 入库"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.material_service = CandidateMaterialService(session)

    async def collect(
        self,
        agent_id: int,
        agent_name: str,
        platform_configs: list[dict],
        filter_keywords: list[str] | None = None,
        keyword_rules: list[KeywordRule] | None = None,
    ) -> list[int]:
        """完整采集流程: 抓取 → 过滤 → 评分 → 入库

        Args:
            agent_id: Agent ID
            agent_name: Agent 名称 (用于 source_identity)
            platform_configs: 平台配置列表, 每项 {"platform_id": "toutiao", ...}
            filter_keywords: 简单关键词列表 (自动转为 optional 规则)
            keyword_rules: 已解析的关键词规则 (优先于 filter_keywords)

        Returns:
            创建的 CandidateMaterial ID 列表
        """
        # 1. 收集要抓取的平台 ID
        platform_ids = []
        for cfg in platform_configs:
            pid = cfg.get("platform_id", "")
            if pid:
                platform_ids.append(pid)

        if not platform_ids:
            logger.warning("No platform IDs configured for agent %s", agent_name)
            return []

        # 2. 并发抓取
        platform_results = await fetch_platforms_batch(platform_ids)

        # Flatten all items
        all_items: list[TrendingItem] = []
        for pid, items in platform_results.items():
            all_items.extend(items)

        if not all_items:
            logger.info("No trending items fetched for agent %s", agent_name)
            return []

        # 3. 关键词过滤
        rules = keyword_rules
        if not rules and filter_keywords:
            # Convert simple keywords to a single optional rule
            rules = [KeywordRule(optional=filter_keywords)]

        if rules:
            filtered = filter_items(all_items, rules)
            logger.info(
                "Keyword filter: %d → %d items for agent %s",
                len(all_items), len(filtered), agent_name,
            )
        else:
            filtered = all_items

        # 4. 计算跨平台权重
        # Group by title for cross-platform frequency
        title_map: dict[str, list[TrendingItem]] = {}
        for item in filtered:
            key = item.title.strip().lower()
            title_map.setdefault(key, []).append(item)

        # 5. 入库
        created_ids: list[int] = []
        seen_titles: set[str] = set()

        for title_key, group in title_map.items():
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            # Pick the best-ranked item as representative
            best = min(group, key=lambda x: x.rank)
            all_ranks = [item.rank for item in group]
            count = len(group)

            weight = calculate_trending_weight(best.rank, count=count, ranks=all_ranks)
            quality = weight_to_quality_score(weight)

            # Collect platform names for metadata
            platforms = list({item.platform_name for item in group})

            data = CandidateMaterialCreate(
                source_type="trending",
                source_identity=best.platform_name,
                original_url=best.url,
                title=best.title,
                summary=f"热榜来源: {', '.join(platforms)} | 最高排名: #{best.rank}",
                raw_content="",
                metadata={
                    "platform_id": best.platform_id,
                    "platform_name": best.platform_name,
                    "rank": best.rank,
                    "hot_value": best.hot_value,
                    "cross_platform_count": count,
                    "all_platforms": platforms,
                    "all_ranks": all_ranks,
                    "trending_weight": round(weight, 2),
                },
                tags=["trending"] + [f"platform:{p}" for p in platforms],
                agent_id=agent_id,
                quality_score=round(quality, 4),
            )

            material = await self.material_service.ingest(data, agent_name=agent_name)
            created_ids.append(material.id)

        logger.info(
            "TrendingCollector: collected %d materials (from %d raw items) for agent %s",
            len(created_ids), len(all_items), agent_name,
        )
        return created_ids
