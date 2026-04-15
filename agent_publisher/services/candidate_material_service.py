from __future__ import annotations

import hashlib
import logging

from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.candidate_material import CandidateMaterial
from agent_publisher.schemas.candidate_material import (
    CandidateMaterialCreate,
    CandidateMaterialListParams,
    CandidateMaterialTagUpdate,
)

logger = logging.getLogger(__name__)

# Minimum quality score to pass the quality gate
MIN_QUALITY_SCORE = 0.3


class CandidateMaterialService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Ingest: unified entry point for all sources
    # ------------------------------------------------------------------

    async def ingest(
        self,
        data: CandidateMaterialCreate,
        agent_name: str | None = None,
    ) -> CandidateMaterial:
        """Ingest a candidate material into the pool.

        Automatically applies source tags, agent identity tags,
        runs duplicate detection, and quality gate check.
        """
        # Build auto tags
        auto_tags: list[str] = list(data.tags) if data.tags else []
        # Always add source type tag
        if data.source_type not in auto_tags:
            auto_tags.append(data.source_type)
        # Add agent identity tag if available
        if agent_name:
            agent_tag = f"agent:{agent_name}"
            if agent_tag not in auto_tags:
                auto_tags.append(agent_tag)

        # Duplicate detection
        is_dup = await self._check_duplicate(data.original_url, data.title)

        material = CandidateMaterial(
            source_type=data.source_type,
            source_identity=data.source_identity,
            original_url=data.original_url,
            title=data.title,
            summary=data.summary,
            raw_content=data.raw_content,
            extra_metadata=data.metadata,
            tags=auto_tags,
            agent_id=data.agent_id,
            is_duplicate=is_dup,
            quality_score=data.quality_score,
            status="pending",
        )
        self.session.add(material)
        await self.session.commit()
        await self.session.refresh(material)

        # Audit log
        logger.info(
            "AUDIT: material_ingested id=%d source_type=%s source_identity=%s "
            "agent_id=%s is_duplicate=%s quality=%s tags=%s",
            material.id,
            material.source_type,
            material.source_identity,
            material.agent_id,
            material.is_duplicate,
            material.quality_score,
            material.tags,
        )
        return material

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    async def _check_duplicate(self, url: str, title: str) -> bool:
        """Check if a material with the same URL or very similar title already exists."""
        if url:
            hashlib.md5(url.encode()).hexdigest()
            stmt = select(CandidateMaterial).where(CandidateMaterial.original_url == url).limit(1)
            result = await self.session.execute(stmt)
            if result.scalars().first():
                return True

        # Simple title-based duplicate check (exact match)
        if title:
            stmt = select(CandidateMaterial).where(CandidateMaterial.title == title).limit(1)
            result = await self.session.execute(stmt)
            if result.scalars().first():
                return True

        return False

    # ------------------------------------------------------------------
    # Quality gate
    # ------------------------------------------------------------------

    @staticmethod
    def passes_quality_gate(material: CandidateMaterial) -> bool:
        """Check if a material meets the minimum quality threshold."""
        if material.quality_score is not None and material.quality_score < MIN_QUALITY_SCORE:
            return False
        if material.is_duplicate:
            return False
        return True

    # ------------------------------------------------------------------
    # Tag management
    # ------------------------------------------------------------------

    async def update_tags(
        self, material_id: int, tag_update: CandidateMaterialTagUpdate
    ) -> CandidateMaterial | None:
        """Add or remove custom tags from a material."""
        material = await self.session.get(CandidateMaterial, material_id)
        if not material:
            return None

        current_tags: list[str] = list(material.tags or [])
        # Add new tags
        for tag in tag_update.add_tags:
            if tag not in current_tags:
                current_tags.append(tag)
        # Remove tags
        for tag in tag_update.remove_tags:
            if tag in current_tags:
                current_tags.remove(tag)

        material.tags = current_tags
        await self.session.commit()
        await self.session.refresh(material)
        return material

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_by_id(self, material_id: int) -> CandidateMaterial | None:
        return await self.session.get(CandidateMaterial, material_id)

    async def list_materials(
        self, params: CandidateMaterialListParams
    ) -> tuple[list[CandidateMaterial], int]:
        """List candidate materials with filtering and pagination.

        Returns (items, total_count).
        """
        conditions = []
        if params.agent_id is not None:
            conditions.append(CandidateMaterial.agent_id == params.agent_id)
        if params.source_type is not None:
            conditions.append(CandidateMaterial.source_type == params.source_type)
        if params.status is not None:
            conditions.append(CandidateMaterial.status == params.status)
        if params.start_date is not None:
            conditions.append(CandidateMaterial.created_at >= params.start_date)
        if params.end_date is not None:
            conditions.append(CandidateMaterial.created_at <= params.end_date)

        base_where = and_(*conditions) if conditions else True

        # Count
        count_stmt = select(func.count(CandidateMaterial.id)).where(base_where)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Fetch page
        offset = (params.page - 1) * params.page_size
        stmt = (
            select(CandidateMaterial)
            .where(base_where)
            .order_by(CandidateMaterial.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        # Post-filter by tags (JSON contains) – done in Python for SQLite compat
        if params.tags:
            items = [m for m in items if m.tags and all(t in m.tags for t in params.tags)]

        return items, total

    async def list_pending_for_agent(
        self, agent_id: int, limit: int = 20
    ) -> list[CandidateMaterial]:
        """Get pending, non-duplicate materials for an agent, sorted by quality."""
        stmt = (
            select(CandidateMaterial)
            .where(
                CandidateMaterial.agent_id == agent_id,
                CandidateMaterial.status == "pending",
                CandidateMaterial.is_duplicate.is_(False),
            )
            .order_by(CandidateMaterial.quality_score.desc().nulls_last())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_accepted(self, material_id: int) -> None:
        material = await self.session.get(CandidateMaterial, material_id)
        if material:
            material.status = "accepted"
            await self.session.commit()

    async def mark_rejected(self, material_id: int) -> None:
        material = await self.session.get(CandidateMaterial, material_id)
        if material:
            material.status = "rejected"
            await self.session.commit()
