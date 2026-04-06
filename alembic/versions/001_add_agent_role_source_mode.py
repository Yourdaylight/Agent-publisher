"""create base tables: accounts, agents, articles, tasks, and add agent role/source fields

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
    # --- accounts ---
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('appid', sa.String(100), unique=True, nullable=False),
        sa.Column('appsecret', sa.String(200), nullable=False),
        sa.Column('owner_email', sa.String(200), server_default=''),
        sa.Column('ip_whitelist', sa.String(500), server_default=''),
        sa.Column('access_token', sa.String(600), server_default=''),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- llm_profiles ---
    op.create_table(
        'llm_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), server_default='openai'),
        sa.Column('model', sa.String(100), server_default='gpt-4o'),
        sa.Column('api_key', sa.String(300), server_default='', nullable=True),
        sa.Column('base_url', sa.String(500), server_default='', nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default='0'),
        sa.Column('description', sa.Text(), server_default='', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- agents (with all columns including role/source from the start) ---
    op.create_table(
        'agents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('topic', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('rss_sources', sa.JSON(), server_default='[]'),
        # Agent role & source columns
        sa.Column('role', sa.String(50), nullable=False, server_default='full_pipeline'),
        sa.Column('source_mode', sa.String(50), nullable=False, server_default='rss'),
        sa.Column('search_config', sa.JSON(), nullable=True),
        sa.Column('allowed_skill_sources', sa.JSON(), nullable=True),
        # LLM config
        sa.Column('llm_profile_id', sa.Integer(), sa.ForeignKey('llm_profiles.id'), nullable=True),
        sa.Column('llm_provider', sa.String(50), server_default='', nullable=True),
        sa.Column('llm_model', sa.String(100), server_default='', nullable=True),
        sa.Column('llm_api_key', sa.String(300), server_default='', nullable=True),
        sa.Column('llm_base_url', sa.String(500), server_default='', nullable=True),
        sa.Column('prompt_template', sa.Text(), server_default=''),
        sa.Column('image_style', sa.String(500), server_default='现代简约风格，色彩鲜明'),
        sa.Column('default_style_id', sa.String(50), nullable=True),
        sa.Column('schedule_cron', sa.String(50), server_default='0 8 * * *'),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('is_builtin', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_agents_account_id', 'agents', ['account_id'])

    # --- articles ---
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('digest', sa.String(500), server_default=''),
        sa.Column('content', sa.Text(), server_default=''),
        sa.Column('html_content', sa.Text(), server_default=''),
        sa.Column('cover_image_url', sa.String(500), server_default=''),
        sa.Column('images', sa.JSON(), server_default='[]'),
        sa.Column('source_news', sa.JSON(), server_default='[]'),
        sa.Column('status', sa.String(20), server_default='draft'),
        sa.Column('wechat_media_id', sa.String(200), server_default=''),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_article_id', sa.Integer(), sa.ForeignKey('articles.id'), nullable=True),
        sa.Column('variant_style', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_articles_agent_id', 'articles', ['agent_id'])
    op.create_index('ix_articles_status', 'articles', ['status'])

    # --- tasks ---
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id'), nullable=True),
        sa.Column('task_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('result', sa.JSON(), server_default='{}'),
        sa.Column('steps', sa.JSON(), server_default='[]'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_tasks_agent_id', 'tasks', ['agent_id'])


def downgrade() -> None:
    op.drop_index('ix_tasks_agent_id', 'tasks')
    op.drop_table('tasks')
    op.drop_index('ix_articles_status', 'articles')
    op.drop_index('ix_articles_agent_id', 'articles')
    op.drop_table('articles')
    op.drop_index('ix_agents_account_id', 'agents')
    op.drop_table('agents')
    op.drop_table('llm_profiles')
    op.drop_table('accounts')
