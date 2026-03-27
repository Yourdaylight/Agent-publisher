"""数据源注册中心 — SourceConfig CRUD + Agent 绑定 + 采集编排"""
from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_publisher.models.agent import Agent
from agent_publisher.models.source_config import AgentSourceBinding, SourceConfig
from agent_publisher.schemas.source_config import (
    AgentSourceBindingCreate,
    SourceConfigCreate,
    SourceConfigUpdate,
    TRENDING_PLATFORMS,
)
from agent_publisher.services.trending_service import (
    KeywordRule,
    TrendingCollectorService,
    parse_keyword_rules,
)

logger = logging.getLogger(__name__)


class SourceRegistryService:
    """数据源注册中心 — CRUD + Agent 绑定 + 采集编排"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ──────────────────────────────────────────────────────────────────
    # SourceConfig CRUD
    # ──────────────────────────────────────────────────────────────────

    async def create_source(self, data: SourceConfigCreate) -> SourceConfig:
        """创建数据源"""
        source = SourceConfig(
            source_type=data.source_type,
            source_key=data.source_key,
            display_name=data.display_name,
            config=data.config,
            is_enabled=data.is_enabled,
            collect_cron=data.collect_cron,
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        logger.info("Created source: %s (%s)", source.source_key, source.display_name)
        return source

    async def update_source(self, source_id: int, data: SourceConfigUpdate) -> SourceConfig | None:
        """更新数据源"""
        source = await self.session.get(SourceConfig, source_id)
        if not source:
            return None

        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(source, field_name, value)

        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete_source(self, source_id: int) -> bool:
        """删除数据源 (级联删除绑定)"""
        source = await self.session.get(SourceConfig, source_id)
        if not source:
            return False

        await self.session.delete(source)
        await self.session.commit()
        logger.info("Deleted source: %s", source.source_key)
        return True

    async def list_sources(
        self,
        source_type: str | None = None,
        is_enabled: bool | None = None,
    ) -> list[SourceConfig]:
        """列表查询数据源"""
        conditions = []
        if source_type is not None:
            conditions.append(SourceConfig.source_type == source_type)
        if is_enabled is not None:
            conditions.append(SourceConfig.is_enabled == is_enabled)

        stmt = select(SourceConfig).order_by(SourceConfig.id)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_source(self, source_id: int) -> SourceConfig | None:
        """获取单个数据源"""
        return await self.session.get(SourceConfig, source_id)

    async def get_source_by_key(self, source_key: str) -> SourceConfig | None:
        """按 source_key 查找"""
        stmt = select(SourceConfig).where(SourceConfig.source_key == source_key)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def toggle_source(self, source_id: int, is_enabled: bool) -> SourceConfig | None:
        """启用/禁用数据源"""
        source = await self.session.get(SourceConfig, source_id)
        if not source:
            return None
        source.is_enabled = is_enabled
        await self.session.commit()
        await self.session.refresh(source)
        return source

    # ──────────────────────────────────────────────────────────────────
    # Agent 绑定管理
    # ──────────────────────────────────────────────────────────────────

    async def bind_agent(
        self,
        agent_id: int,
        data: AgentSourceBindingCreate,
    ) -> AgentSourceBinding:
        """绑定 Agent 到数据源"""
        # Check if already bound
        stmt = select(AgentSourceBinding).where(
            AgentSourceBinding.agent_id == agent_id,
            AgentSourceBinding.source_config_id == data.source_config_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            # Update existing binding
            existing.is_enabled = data.is_enabled
            existing.filter_keywords = data.filter_keywords
            await self.session.commit()
            # Re-fetch with eagerly loaded source_config
            return await self._get_binding_with_source(existing.id)

        binding = AgentSourceBinding(
            agent_id=agent_id,
            source_config_id=data.source_config_id,
            is_enabled=data.is_enabled,
            filter_keywords=data.filter_keywords,
        )
        self.session.add(binding)
        await self.session.commit()
        await self.session.refresh(binding)
        # Re-fetch with eagerly loaded source_config
        return await self._get_binding_with_source(binding.id)

    async def _get_binding_with_source(self, binding_id: int) -> AgentSourceBinding:
        """Fetch a binding with its source_config eagerly loaded."""
        stmt = (
            select(AgentSourceBinding)
            .options(selectinload(AgentSourceBinding.source_config))
            .where(AgentSourceBinding.id == binding_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
        logger.info("Bound agent %d to source %d", agent_id, data.source_config_id)
        return binding

    async def unbind_agent(self, agent_id: int, source_config_id: int) -> bool:
        """解绑 Agent 与数据源"""
        stmt = delete(AgentSourceBinding).where(
            AgentSourceBinding.agent_id == agent_id,
            AgentSourceBinding.source_config_id == source_config_id,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def list_agent_bindings(self, agent_id: int) -> list[AgentSourceBinding]:
        """列出 Agent 的所有数据源绑定"""
        stmt = (
            select(AgentSourceBinding)
            .options(selectinload(AgentSourceBinding.source_config))
            .where(AgentSourceBinding.agent_id == agent_id)
            .order_by(AgentSourceBinding.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_agent_sources_by_type(
        self, agent_id: int, source_type: str
    ) -> list[SourceConfig]:
        """获取 Agent 绑定的某类型数据源"""
        stmt = (
            select(SourceConfig)
            .join(AgentSourceBinding)
            .where(
                AgentSourceBinding.agent_id == agent_id,
                AgentSourceBinding.is_enabled.is_(True),
                SourceConfig.source_type == source_type,
                SourceConfig.is_enabled.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ──────────────────────────────────────────────────────────────────
    # 采集编排
    # ──────────────────────────────────────────────────────────────────

    async def collect_for_agent(self, agent: Agent) -> dict[str, list[int]]:
        """按 agent 绑定的源分发采集

        Returns:
            {"rss": [id, ...], "trending": [id, ...], "search": [id, ...]}
        """
        results: dict[str, list[int]] = {}

        # 获取所有启用的绑定
        bindings = await self.list_agent_bindings(agent.id)
        enabled_bindings = [b for b in bindings if b.is_enabled and b.source_config and b.source_config.is_enabled]

        if not enabled_bindings:
            logger.info("No enabled source bindings for agent %s", agent.name)
            return results

        # 按类型分组
        by_type: dict[str, list[AgentSourceBinding]] = {}
        for binding in enabled_bindings:
            stype = binding.source_config.source_type
            by_type.setdefault(stype, []).append(binding)

        # RSS 采集
        if "rss" in by_type:
            rss_ids = await self._collect_rss(agent, by_type["rss"])
            if rss_ids:
                results["rss"] = rss_ids

        # 热榜采集
        if "trending" in by_type:
            trending_ids = await self._collect_trending(agent, by_type["trending"])
            if trending_ids:
                results["trending"] = trending_ids

        # 搜索采集
        if "search" in by_type:
            search_ids = await self._collect_search(agent, by_type["search"])
            if search_ids:
                results["search"] = search_ids

        total = sum(len(ids) for ids in results.values())
        logger.info(
            "Collected %d total materials for agent %s: %s",
            total, agent.name,
            {k: len(v) for k, v in results.items()},
        )
        return results

    async def _collect_rss(
        self, agent: Agent, bindings: list[AgentSourceBinding]
    ) -> list[int]:
        """RSS 采集 — 复用已有 RssCollectorAdapter"""
        from agent_publisher.services.rss_service import RssCollectorAdapter

        rss_sources = []
        for binding in bindings:
            cfg = binding.source_config.config or {}
            url = cfg.get("url", "")
            if url:
                rss_sources.append({
                    "url": url,
                    "name": binding.source_config.display_name,
                })

        if not rss_sources:
            return []

        adapter = RssCollectorAdapter(self.session)
        return await adapter.collect(
            agent_id=agent.id,
            agent_name=agent.name,
            rss_sources=rss_sources,
        )

    async def _collect_trending(
        self, agent: Agent, bindings: list[AgentSourceBinding]
    ) -> list[int]:
        """热榜采集"""
        platform_configs = []
        all_filter_keywords: list[str] = []

        for binding in bindings:
            cfg = binding.source_config.config or {}
            pid = cfg.get("platform_id", "")
            if pid:
                platform_configs.append({"platform_id": pid})

            # Collect per-binding filter keywords
            if binding.filter_keywords:
                all_filter_keywords.extend(binding.filter_keywords)

        if not platform_configs:
            return []

        collector = TrendingCollectorService(self.session)
        return await collector.collect(
            agent_id=agent.id,
            agent_name=agent.name,
            platform_configs=platform_configs,
            filter_keywords=all_filter_keywords if all_filter_keywords else None,
        )

    async def _collect_search(
        self, agent: Agent, bindings: list[AgentSourceBinding]
    ) -> list[int]:
        """搜索采集 — 复用已有 SearchCollector"""
        from agent_publisher.services.search_collector_service import get_search_collector

        collector = get_search_collector(self.session)
        all_ids: list[int] = []

        for binding in bindings:
            cfg = binding.source_config.config or {}
            ids = await collector.collect(
                agent_id=agent.id,
                agent_name=agent.name,
                search_config=cfg,
            )
            all_ids.extend(ids)

        return all_ids

    # ──────────────────────────────────────────────────────────────────
    # 初始化 — 默认热榜平台 seed
    # ──────────────────────────────────────────────────────────────────

    async def seed_default_sources(self) -> int:
        """启动时自动创建 11 个默认热榜平台 (幂等)

        Returns:
            新创建的数据源数量
        """
        created = 0
        for platform in TRENDING_PLATFORMS:
            source_key = f"trending:{platform['id']}"
            existing = await self.get_source_by_key(source_key)
            if existing:
                continue

            source = SourceConfig(
                source_type="trending",
                source_key=source_key,
                display_name=platform["name"],
                config={"platform_id": platform["id"]},
                is_enabled=True,
            )
            self.session.add(source)
            created += 1

        if created:
            await self.session.commit()
            logger.info("Seeded %d default trending platform sources", created)

        return created
