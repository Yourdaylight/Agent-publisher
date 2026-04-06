"""Add missing tables: style_presets, prompt_templates, source_configs, bindings,
credits, groups, invite_codes, memberships, orders

Revision ID: 005_missing_tables
Revises: 004_media_assets
Create Date: 2026-04-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_missing_tables"
down_revision: Union[str, None] = "004_media_asset_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- style_presets ---
    op.create_table(
        'style_presets',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('style_id', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), server_default=''),
        sa.Column('prompt', sa.Text(), server_default=''),
        sa.Column('is_builtin', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_style_presets_style_id', 'style_presets', ['style_id'])

    # --- prompt_templates ---
    op.create_table(
        'prompt_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('category', sa.String(50), server_default='rewrite'),
        sa.Column('description', sa.String(500), server_default=''),
        sa.Column('content', sa.Text(), server_default=''),
        sa.Column('variables', sa.JSON(), server_default='[]'),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('owner_email', sa.String(200), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_prompt_templates_category', 'prompt_templates', ['category'])
    op.create_index('ix_prompt_templates_owner_email', 'prompt_templates', ['owner_email'])

    # --- source_configs ---
    op.create_table(
        'source_configs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_key', sa.String(200), unique=True, nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default='1'),
        sa.Column('collect_cron', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- agent_source_bindings (many-to-many) ---
    op.create_table(
        'agent_source_bindings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id'), nullable=False),
        sa.Column('source_config_id', sa.Integer(), sa.ForeignKey('source_configs.id'), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='1'),
        sa.Column('filter_keywords', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('agent_id', 'source_config_id', name='uq_agent_source'),
    )

    # --- credits_balance ---
    op.create_table(
        'credits_balance',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_email', sa.String(200), unique=True, nullable=False),
        sa.Column('total_credits', sa.Integer(), server_default='0'),
        sa.Column('used_credits', sa.Integer(), server_default='0'),
        sa.Column('free_credits', sa.Integer(), server_default='50'),
        sa.Column('paid_credits', sa.Integer(), server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_credits_balance_user_email', 'credits_balance', ['user_email'])

    # --- credits_transaction ---
    op.create_table(
        'credits_transaction',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_email', sa.String(200), nullable=False),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('credits_amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_credits_transaction_user_email', 'credits_transaction', ['user_email'])

    # --- user_groups ---
    op.create_table(
        'user_groups',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.String(500), server_default=''),
        sa.Column('created_by', sa.String(200), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- user_group_members ---
    op.create_table(
        'user_group_members',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('user_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(200), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('group_id', 'email', name='uq_group_member'),
    )
    op.create_index('ix_user_group_members_email', 'user_group_members', ['email'])

    # --- invite_codes ---
    op.create_table(
        'invite_codes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('channel', sa.String(50), server_default='open'),
        sa.Column('max_uses', sa.Integer(), server_default='0'),
        sa.Column('used_count', sa.Integer(), server_default='0'),
        sa.Column('bonus_credits', sa.Integer(), server_default='100'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('created_by', sa.String(200), server_default=''),
        sa.Column('note', sa.Text(), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_invite_codes_code', 'invite_codes', ['code'])

    # --- invite_redemptions ---
    op.create_table(
        'invite_redemptions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('invite_code_id', sa.Integer(), sa.ForeignKey('invite_codes.id')),
        sa.Column('user_email', sa.String(200), nullable=False),
        sa.Column('ip_address', sa.String(50), server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_invite_redemptions_user_email', 'invite_redemptions', ['user_email'])

    # --- membership_plans ---
    op.create_table(
        'membership_plans',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('price_monthly', sa.Float(), server_default='0'),
        sa.Column('price_yearly', sa.Float(), server_default='0'),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_membership_plans_name', 'membership_plans', ['name'])

    # --- user_memberships ---
    op.create_table(
        'user_memberships',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_email', sa.String(200), nullable=False),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('membership_plans.id')),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('payment_method', sa.String(50), nullable=True, server_default='manual'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_user_memberships_user_email', 'user_memberships', ['user_email'])

    # --- orders ---
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('order_no', sa.String(64), unique=True, nullable=False),
        sa.Column('user_email', sa.String(200), nullable=False),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('membership_plans.id')),
        sa.Column('amount', sa.Float(), server_default='0'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('payment_method', sa.String(50), nullable=True, server_default='manual'),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_orders_order_no', 'orders', ['order_no'])
    op.create_index('ix_orders_user_email', 'orders', ['user_email'])


def downgrade() -> None:
    # Drop in reverse order of creation
    op.drop_index('ix_orders_user_email', table_name='orders')
    op.drop_index('ix_orders_order_no', table_name='orders')
    op.drop_table('orders')

    op.drop_index('ix_user_memberships_user_email', table_name='user_memberships')
    op.drop_table('user_memberships')

    op.drop_index('ix_membership_plans_name', table_name='membership_plans')
    op.drop_table('membership_plans')

    op.drop_index('ix_invite_redemptions_user_email', table_name='invite_redemptions')
    op.drop_table('invite_redemptions')

    op.drop_index('ix_invite_codes_code', table_name='invite_codes')
    op.drop_table('invite_codes')

    op.drop_index('ix_user_group_members_email', table_name='user_group_members')
    op.drop_table('user_group_members')

    op.drop_table('user_groups')

    op.drop_index('ix_credits_transaction_user_email', table_name='credits_transaction')
    op.drop_table('credits_transaction')

    op.drop_index('ix_credits_balance_user_email', table_name='credits_balance')
    op.drop_table('credits_balance')

    op.drop_table('agent_source_bindings')
    op.drop_table('source_configs')

    op.drop_index('ix_prompt_templates_owner_email', table_name='prompt_templates')
    op.drop_index('ix_prompt_templates_category', table_name='prompt_templates')
    op.drop_table('prompt_templates')

    op.drop_index('ix_style_presets_style_id', table_name='style_presets')
    op.drop_table('style_presets')
