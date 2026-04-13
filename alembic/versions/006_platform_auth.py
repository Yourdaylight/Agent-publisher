"""Add platform auth fields to accounts table + platform_tickets table

Revision ID: 006_platform_auth
Revises: 005_missing_tables
Create Date: 2026-04-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_platform_auth"
down_revision: Union[str, None] = "005_missing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to accounts table
    op.add_column("accounts", sa.Column("auth_mode", sa.String(20), server_default="manual"))
    op.add_column("accounts", sa.Column("authorizer_appid", sa.String(100), server_default=""))
    op.add_column("accounts", sa.Column("authorizer_refresh_token", sa.String(200), server_default=""))
    op.add_column("accounts", sa.Column("authorizer_access_token", sa.String(600), server_default=""))
    op.add_column("accounts", sa.Column("authorizer_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("nick_name", sa.String(200), server_default=""))
    op.add_column("accounts", sa.Column("head_img", sa.String(500), server_default=""))
    op.add_column("accounts", sa.Column("service_type", sa.Integer(), server_default="0"))
    op.add_column("accounts", sa.Column("verify_type", sa.Integer(), server_default="0"))

    # Create platform_tickets table
    op.create_table(
        "platform_tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket", sa.String(200), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop platform_tickets table
    op.drop_table("platform_tickets")

    # Remove new columns from accounts table
    op.drop_column("accounts", "verify_type")
    op.drop_column("accounts", "service_type")
    op.drop_column("accounts", "head_img")
    op.drop_column("accounts", "nick_name")
    op.drop_column("accounts", "authorizer_token_expires_at")
    op.drop_column("accounts", "authorizer_access_token")
    op.drop_column("accounts", "authorizer_refresh_token")
    op.drop_column("accounts", "authorizer_appid")
    op.drop_column("accounts", "auth_mode")
