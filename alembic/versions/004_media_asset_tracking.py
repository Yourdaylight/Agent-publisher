"""add media asset tracking

Revision ID: 004_media_asset_tracking
Revises: 003_multi_account_publish
Create Date: 2026-03-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_media_asset_tracking"
down_revision: Union[str, None] = "003_multi_account_publish"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create media_assets table if not exists (may be missing in fresh DB)
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(255), nullable=False, server_default=""),
        sa.Column("file_type", sa.String(50), nullable=False, server_default="image"),
        sa.Column("storage_path", sa.String(1000), server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(100), server_default=""),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.Text(), server_default=""),
        # Columns originally added by this migration
        sa.Column("source_kind", sa.String(length=50), server_default="manual", nullable=False),
        sa.Column("source_url", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_media_assets_file_type", "media_assets", ["file_type"])
    op.create_index("ix_media_assets_article_id", "media_assets", ["article_id"])
    op.create_index("ix_media_assets_source_kind", "media_assets", ["source_kind"])

    # Create media_asset_wechat_mappings table
    op.create_table(
        "media_asset_wechat_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("media_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("wechat_url", sa.String(length=1000), server_default=""),
        sa.Column("upload_status", sa.String(length=20), server_default="pending"),
        sa.Column("error_message", sa.Text(), server_default=""),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "media_asset_id",
            "account_id",
            name="uq_media_asset_wechat_mapping_asset_account",
        ),
    )
    op.create_index(
        "ix_media_asset_wechat_mappings_media_asset_id",
        "media_asset_wechat_mappings",
        ["media_asset_id"],
    )
    op.create_index(
        "ix_media_asset_wechat_mappings_account_id",
        "media_asset_wechat_mappings",
        ["account_id"],
    )
    op.create_index(
        "ix_media_asset_wechat_mappings_upload_status",
        "media_asset_wechat_mappings",
        ["upload_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_media_asset_wechat_mappings_upload_status", table_name="media_asset_wechat_mappings"
    )
    op.drop_index(
        "ix_media_asset_wechat_mappings_account_id", table_name="media_asset_wechat_mappings"
    )
    op.drop_index(
        "ix_media_asset_wechat_mappings_media_asset_id", table_name="media_asset_wechat_mappings"
    )
    op.drop_table("media_asset_wechat_mappings")

    op.drop_index("ix_media_assets_source_kind", "media_assets")
    op.drop_index("ix_media_assets_article_id", "media_assets")
    op.drop_index("ix_media_assets_file_type", "media_assets")
    op.drop_table("media_assets")
