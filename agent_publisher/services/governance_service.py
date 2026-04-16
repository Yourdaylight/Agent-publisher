"""Governance service: source statistics, tag distribution, and governance rules."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.candidate_material import CandidateMaterial

logger = logging.getLogger(__name__)


class GovernanceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_source_mode_stats(self, owner_email: str | None = None) -> list[dict]:
        """Calculate per-source-type statistics.

        Returns list of dicts with: source_type, total, accepted, rejected,
        duplicate_count, acceptance_rate, duplicate_rate, conversion_rate.
        If owner_email is provided, only materials belonging to that user's agents are counted.
        """
        # Material counts by source_type
        stmt = select(
            CandidateMaterial.source_type,
            func.count(CandidateMaterial.id).label("total"),
            func.sum(case((CandidateMaterial.status == "accepted", 1), else_=0)).label("accepted"),
            func.sum(case((CandidateMaterial.status == "rejected", 1), else_=0)).label("rejected"),
            func.sum(case((CandidateMaterial.is_duplicate.is_(True), 1), else_=0)).label(
                "duplicate_count"
            ),
        ).group_by(CandidateMaterial.source_type)
        if owner_email:
            stmt = (
                stmt.join(Agent, CandidateMaterial.agent_id == Agent.id)
                .join(Account, Agent.account_id == Account.id)
                .where(Account.owner_email == owner_email)
            )
        result = await self.session.execute(stmt)
        rows = result.all()

        # Article count for conversion rate
        article_count_stmt = select(func.count(Article.id))
        if owner_email:
            article_count_stmt = (
                select(func.count(Article.id))
                .join(Agent, Article.agent_id == Agent.id)
                .join(Account, Agent.account_id == Account.id)
                .where(Account.owner_email == owner_email)
            )
        total_articles = (await self.session.execute(article_count_stmt)).scalar() or 0

        stats = []
        for row in rows:
            total = row.total or 0
            accepted = row.accepted or 0
            rejected = row.rejected or 0
            dup = row.duplicate_count or 0
            stats.append(
                {
                    "source_type": row.source_type,
                    "total": total,
                    "accepted": accepted,
                    "rejected": rejected,
                    "pending": total - accepted - rejected,
                    "duplicate_count": dup,
                    "acceptance_rate": round(accepted / total, 4) if total > 0 else 0,
                    "duplicate_rate": round(dup / total, 4) if total > 0 else 0,
                    "conversion_rate": round(accepted / total_articles, 4)
                    if total_articles > 0
                    else 0,
                }
            )
        return stats

    async def get_tag_stats(self, owner_email: str | None = None) -> list[dict]:
        """Calculate per-tag statistics.

        Since tags are stored as JSON arrays, we need to process them in Python.
        Returns list of dicts with: tag, total, accepted, acceptance_rate.
        """
        stmt = select(
            CandidateMaterial.tags,
            CandidateMaterial.status,
        ).where(CandidateMaterial.tags.isnot(None))
        if owner_email:
            stmt = (
                stmt.join(Agent, CandidateMaterial.agent_id == Agent.id)
                .join(Account, Agent.account_id == Account.id)
                .where(Account.owner_email == owner_email)
            )

        result = await self.session.execute(stmt)
        rows = result.all()

        tag_counts: dict[str, dict] = {}
        for tags_json, status in rows:
            if not tags_json:
                continue
            tags = tags_json if isinstance(tags_json, list) else []
            for tag in tags:
                if tag not in tag_counts:
                    tag_counts[tag] = {"total": 0, "accepted": 0}
                tag_counts[tag]["total"] += 1
                if status == "accepted":
                    tag_counts[tag]["accepted"] += 1

        stats = []
        for tag, counts in sorted(tag_counts.items(), key=lambda x: x[1]["total"], reverse=True):
            total = counts["total"]
            accepted = counts["accepted"]
            stats.append(
                {
                    "tag": tag,
                    "total": total,
                    "accepted": accepted,
                    "acceptance_rate": round(accepted / total, 4) if total > 0 else 0,
                }
            )
        return stats

    async def get_daily_intake_trend(
        self, days: int = 30, owner_email: str | None = None
    ) -> list[dict]:
        """Daily material intake trend for the last N days."""
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(
                func.date(CandidateMaterial.created_at).label("date"),
                CandidateMaterial.source_type,
                func.count(CandidateMaterial.id).label("count"),
            )
            .where(CandidateMaterial.created_at >= since)
            .group_by(func.date(CandidateMaterial.created_at), CandidateMaterial.source_type)
            .order_by(func.date(CandidateMaterial.created_at))
        )
        if owner_email:
            stmt = (
                stmt.join(Agent, CandidateMaterial.agent_id == Agent.id)
                .join(Account, Agent.account_id == Account.id)
                .where(Account.owner_email == owner_email)
            )
        result = await self.session.execute(stmt)
        return [
            {"date": str(row.date), "source_type": row.source_type, "count": row.count}
            for row in result.all()
        ]
