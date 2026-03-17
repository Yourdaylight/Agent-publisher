"""Migrate legacy single-account publish data to multi-account relations.

This script scans articles that have a wechat_media_id (published via old
single-account flow) but lack a corresponding ArticlePublishRelation, and
creates the missing relation records for backward compatibility.

Usage:
    python -m scripts.migrate_legacy_publish_relations
    # or: uv run scripts/migrate_legacy_publish_relations.py
"""
from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


async def migrate(session: AsyncSession, *, dry_run: bool = False) -> dict:
    """Create ArticlePublishRelation records for legacy single-account publishes.

    For each published article that has article.wechat_media_id but no
    corresponding ArticlePublishRelation, this function creates a relation
    using agent.account_id as the target account.

    Returns a summary dict with counts of created, skipped, and error records.
    """
    from agent_publisher.models.agent import Agent
    from agent_publisher.models.article import Article
    from agent_publisher.models.article_publish_relation import ArticlePublishRelation

    # Find all published articles with wechat_media_id
    stmt = select(Article).where(
        Article.wechat_media_id != '',
        Article.wechat_media_id.isnot(None),
    )
    result = await session.execute(stmt)
    articles = result.scalars().all()

    created = 0
    skipped = 0
    errors = 0

    for article in articles:
        # Check if a relation already exists
        rel_stmt = select(ArticlePublishRelation).where(
            ArticlePublishRelation.article_id == article.id,
        )
        rel_result = await session.execute(rel_stmt)
        existing = rel_result.scalars().first()
        if existing:
            skipped += 1
            logger.debug(
                'Article %d already has relation(s), skipping.',
                article.id,
            )
            continue

        # Resolve agent → account
        agent = await session.get(Agent, article.agent_id)
        if not agent:
            logger.warning(
                'Article %d: agent %d not found, skipping.',
                article.id,
                article.agent_id,
            )
            errors += 1
            continue

        account_id = agent.account_id
        if not account_id:
            logger.warning(
                'Article %d: agent %d has no account_id, skipping.',
                article.id,
                article.agent_id,
            )
            errors += 1
            continue

        # Create the relation
        relation = ArticlePublishRelation(
            article_id=article.id,
            account_id=account_id,
            wechat_media_id=article.wechat_media_id,
            publish_status='success',
            sync_status='synced',
            last_error='',
            last_published_at=article.published_at,
            last_synced_at=article.published_at,
        )

        if dry_run:
            logger.info(
                '[DRY RUN] Would create relation: article=%d account=%d media_id=%s',
                article.id,
                account_id,
                article.wechat_media_id,
            )
        else:
            session.add(relation)
            logger.info(
                'Created relation: article=%d account=%d media_id=%s',
                article.id,
                account_id,
                article.wechat_media_id,
            )
        created += 1

    if not dry_run:
        await session.commit()

    summary = {
        'total_articles': len(articles),
        'created': created,
        'skipped': skipped,
        'errors': errors,
    }
    logger.info('Migration summary: %s', summary)
    return summary


async def main():
    from agent_publisher.database import async_session_factory

    dry_run = '--dry-run' in sys.argv
    if dry_run:
        logger.info('Running in DRY RUN mode — no changes will be committed.')

    async with async_session_factory() as session:
        summary = await migrate(session, dry_run=dry_run)

    print(f'\nMigration complete: {summary}')
    if dry_run:
        print('(DRY RUN — re-run without --dry-run to apply changes)')


if __name__ == '__main__':
    asyncio.run(main())
