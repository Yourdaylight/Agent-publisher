"""add agent role and source mode fields

Revision ID: 001_agent_role_source
Revises:
Create Date: 2026-03-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_agent_role_source"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("role", sa.String(50), nullable=False, server_default="full_pipeline"))
    op.add_column("agents", sa.Column("source_mode", sa.String(50), nullable=False, server_default="rss"))
    op.add_column("agents", sa.Column("search_config", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("allowed_skill_sources", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "allowed_skill_sources")
    op.drop_column("agents", "search_config")
    op.drop_column("agents", "source_mode")
    op.drop_column("agents", "role")
