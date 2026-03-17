"""add multi account publish relations

Revision ID: 003_multi_account_publish
Revises: 002_candidate_materials
Create Date: 2026-03-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003_multi_account_publish'
down_revision: Union[str, None] = '002_candidate_materials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'article_publish_relations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('article_id', sa.Integer(), sa.ForeignKey('articles.id'), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id'), nullable=False),
        sa.Column('wechat_media_id', sa.String(length=200), server_default=''),
        sa.Column('publish_status', sa.String(length=20), server_default='pending'),
        sa.Column('sync_status', sa.String(length=20), server_default='pending'),
        sa.Column('last_error', sa.Text(), server_default=''),
        sa.Column('last_published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            'article_id',
            'account_id',
            name='uq_article_publish_relations_article_account',
        ),
    )
    op.create_index(
        'ix_article_publish_relations_article_id',
        'article_publish_relations',
        ['article_id'],
    )
    op.create_index(
        'ix_article_publish_relations_account_id',
        'article_publish_relations',
        ['account_id'],
    )
    op.create_index(
        'ix_article_publish_relations_publish_status',
        'article_publish_relations',
        ['publish_status'],
    )
    op.create_index(
        'ix_article_publish_relations_sync_status',
        'article_publish_relations',
        ['sync_status'],
    )

    with op.batch_alter_table('publish_records', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('account_id', sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            'fk_publish_records_account_id', 'accounts', ['account_id'], ['id'],
        )
        batch_op.create_index('ix_publish_records_account_id', ['account_id'])


def downgrade() -> None:
    with op.batch_alter_table('publish_records', schema=None) as batch_op:
        batch_op.drop_index('ix_publish_records_account_id')
        batch_op.drop_column('account_id')

    op.drop_index(
        'ix_article_publish_relations_sync_status',
        table_name='article_publish_relations',
    )
    op.drop_index(
        'ix_article_publish_relations_publish_status',
        table_name='article_publish_relations',
    )
    op.drop_index(
        'ix_article_publish_relations_account_id',
        table_name='article_publish_relations',
    )
    op.drop_index(
        'ix_article_publish_relations_article_id',
        table_name='article_publish_relations',
    )
    op.drop_table('article_publish_relations')
