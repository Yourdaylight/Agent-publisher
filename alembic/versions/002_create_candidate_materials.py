"""create candidate_materials table

Revision ID: 002_candidate_materials
Revises: 001_agent_role_source
Create Date: 2026-03-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_candidate_materials"
down_revision: Union[str, None] = "001_agent_role_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_identity", sa.String(200), server_default=""),
        sa.Column("original_url", sa.String(1000), server_default=""),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), server_default=""),
        sa.Column("raw_content", sa.Text(), server_default=""),
        sa.Column("extra_metadata", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_materials_agent_id", "candidate_materials", ["agent_id"])
    op.create_index("ix_candidate_materials_source_type", "candidate_materials", ["source_type"])
    op.create_index("ix_candidate_materials_status", "candidate_materials", ["status"])
    op.create_index("ix_candidate_materials_created_at", "candidate_materials", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_candidate_materials_created_at", "candidate_materials")
    op.drop_index("ix_candidate_materials_status", "candidate_materials")
    op.drop_index("ix_candidate_materials_source_type", "candidate_materials")
    op.drop_index("ix_candidate_materials_agent_id", "candidate_materials")
    op.drop_table("candidate_materials")
