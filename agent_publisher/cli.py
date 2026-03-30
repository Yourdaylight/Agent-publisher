from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="agent-pub", help="AI-driven multi-account WeChat article publisher")
console = Console()

# --- helpers ---


def _run(coro):
    """Run an async function synchronously."""
    return asyncio.run(coro)


async def _get_session():
    from agent_publisher.database import async_session_factory

    return async_session_factory()


# ==================== Account ====================

account_app = typer.Typer(help="Manage WeChat accounts")
app.add_typer(account_app, name="account")


@account_app.command("add")
def account_add(
    name: str = typer.Option(..., help="Account display name"),
    appid: str = typer.Option(..., help="WeChat AppID"),
    appsecret: str = typer.Option(..., help="WeChat AppSecret"),
    ip_whitelist: str = typer.Option("", help="IP whitelist note"),
):
    """Add a WeChat account."""

    async def _add():
        from agent_publisher.models.account import Account

        async with await _get_session() as session:
            account = Account(
                name=name, appid=appid, appsecret=appsecret, ip_whitelist=ip_whitelist
            )
            session.add(account)
            await session.commit()
            await session.refresh(account)
            console.print(f"[green]Account created: id={account.id} name={account.name}[/green]")

    _run(_add())


@account_app.command("list")
def account_list():
    """List all WeChat accounts."""

    async def _list():
        from sqlalchemy import select

        from agent_publisher.models.account import Account

        async with await _get_session() as session:
            result = await session.execute(select(Account).order_by(Account.id))
            accounts = result.scalars().all()
            table = Table(title="WeChat Accounts")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("AppID")
            table.add_column("IP Whitelist")
            table.add_column("Created")
            for a in accounts:
                table.add_row(str(a.id), a.name, a.appid, a.ip_whitelist, str(a.created_at))
            console.print(table)

    _run(_list())


@account_app.command("remove")
def account_remove(account_id: int = typer.Argument(..., help="Account ID")):
    """Remove a WeChat account."""

    async def _remove():
        from agent_publisher.models.account import Account

        async with await _get_session() as session:
            account = await session.get(Account, account_id)
            if not account:
                console.print(f"[red]Account {account_id} not found[/red]")
                raise typer.Exit(1)
            await session.delete(account)
            await session.commit()
            console.print(f"[green]Account {account_id} removed[/green]")

    _run(_remove())


# ==================== Agent ====================

agent_app = typer.Typer(help="Manage agents")
app.add_typer(agent_app, name="agent")


@agent_app.command("add")
def agent_add(
    name: str = typer.Option(..., help="Agent name"),
    topic: str = typer.Option(..., help="Agent topic"),
    account_id: int = typer.Option(..., help="Bound account ID"),
    rss: list[str] = typer.Option([], help="RSS source URLs"),
    description: str = typer.Option("", help="Agent description / system prompt"),
):
    """Create a new agent."""

    async def _add():
        from agent_publisher.models.agent import Agent

        rss_sources = [{"url": url, "name": ""} for url in rss]
        async with await _get_session() as session:
            agent = Agent(
                name=name,
                topic=topic,
                account_id=account_id,
                rss_sources=rss_sources,
                description=description,
            )
            session.add(agent)
            await session.commit()
            await session.refresh(agent)
            console.print(f"[green]Agent created: id={agent.id} name={agent.name}[/green]")

    _run(_add())


@agent_app.command("list")
def agent_list():
    """List all agents."""

    async def _list():
        from sqlalchemy import select

        from agent_publisher.models.agent import Agent

        async with await _get_session() as session:
            result = await session.execute(select(Agent).order_by(Agent.id))
            agents = result.scalars().all()
            table = Table(title="Agents")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Topic")
            table.add_column("Account ID")
            table.add_column("LLM")
            table.add_column("Active")
            table.add_column("Cron")
            for a in agents:
                table.add_row(
                    str(a.id), a.name, a.topic, str(a.account_id),
                    f"{a.llm_provider}/{a.llm_model}", str(a.is_active), a.schedule_cron,
                )
            console.print(table)

    _run(_list())


@agent_app.command("config")
def agent_config(
    agent_id: int = typer.Argument(..., help="Agent ID"),
    llm_provider: Optional[str] = typer.Option(None, help="LLM provider"),
    llm_model: Optional[str] = typer.Option(None, help="LLM model"),
    llm_api_key: Optional[str] = typer.Option(None, help="LLM API key"),
    image_style: Optional[str] = typer.Option(None, help="Image style"),
    schedule_cron: Optional[str] = typer.Option(None, help="Cron expression"),
    is_active: Optional[bool] = typer.Option(None, help="Active flag"),
):
    """Update agent configuration."""

    async def _config():
        from agent_publisher.models.agent import Agent

        async with await _get_session() as session:
            agent = await session.get(Agent, agent_id)
            if not agent:
                console.print(f"[red]Agent {agent_id} not found[/red]")
                raise typer.Exit(1)
            updates = {
                k: v for k, v in {
                    "llm_provider": llm_provider, "llm_model": llm_model,
                    "llm_api_key": llm_api_key, "image_style": image_style,
                    "schedule_cron": schedule_cron, "is_active": is_active,
                }.items() if v is not None
            }
            for key, value in updates.items():
                setattr(agent, key, value)
            await session.commit()
            console.print(f"[green]Agent {agent_id} updated: {list(updates.keys())}[/green]")

    _run(_config())


# ==================== Article ====================

article_app = typer.Typer(help="Article operations")
app.add_typer(article_app, name="article")


@article_app.command("generate")
def article_generate(agent_id: int = typer.Argument(..., help="Agent ID")):
    """Generate an article for a specific agent."""

    async def _generate():
        from agent_publisher.services.task_service import TaskService

        async with await _get_session() as session:
            task_svc = TaskService(session)
            console.print(f"[yellow]Generating article for agent {agent_id}...[/yellow]")
            task = await task_svc.run_generate(agent_id)
            if task.status == "success":
                console.print(f"[green]Article generated! Task={task.id}[/green]")
                console.print(f"  Result: {task.result}")
            else:
                console.print(f"[red]Generation failed: {task.result}[/red]")

    _run(_generate())


@article_app.command("preview")
def article_preview(article_id: int = typer.Argument(..., help="Article ID")):
    """Preview an article."""

    async def _preview():
        from agent_publisher.models.article import Article

        async with await _get_session() as session:
            article = await session.get(Article, article_id)
            if not article:
                console.print(f"[red]Article {article_id} not found[/red]")
                raise typer.Exit(1)
            console.print(f"[bold]{article.title}[/bold]")
            console.print(f"[dim]Status: {article.status} | Created: {article.created_at}[/dim]")
            console.print(f"[italic]{article.digest}[/italic]\n")
            console.print(article.content)

    _run(_preview())


@article_app.command("publish")
def article_publish(
    article_id: int = typer.Argument(..., help="Article ID"),
    account_id: list[int] = typer.Option([], "--account-id", help="Target account ID, repeatable"),
):
    """Publish an article to one or more WeChat draft boxes."""

    async def _publish():
        from agent_publisher.services.article_service import ArticleService

        async with await _get_session() as session:
            svc = ArticleService(session)
            console.print(f"[yellow]Publishing article {article_id}...[/yellow]")
            try:
                publish_result = await svc.publish_article(
                    article_id,
                    target_account_ids=account_id or None,
                )
                status_style = "green" if publish_result.ok else "yellow"
                console.print(
                    f"[{status_style}]Publish finished: overall_status={publish_result.overall_status}[/{status_style}]"
                )
                result_table = Table(title=f"Article {article_id} publish results")
                result_table.add_column("Account ID", style="cyan")
                result_table.add_column("Account")
                result_table.add_column("Status")
                result_table.add_column("Media ID")
                result_table.add_column("Error")
                for item in publish_result.results:
                    row_style = "green" if item.status == "success" else "yellow"
                    result_table.add_row(
                        str(item.account_id),
                        item.account_name,
                        f"[{row_style}]{item.status}[/{row_style}]",
                        item.wechat_media_id or "-",
                        item.error or "-",
                    )
                console.print(result_table)
            except Exception as e:
                console.print(f"[red]Publish failed: {e}[/red]")

    _run(_publish())


# ==================== Run (batch) ====================

@app.command("run")
def run_batch(
    all_agents: bool = typer.Option(False, "--all", help="Run all active agents"),
    agent_id: Optional[str] = typer.Option(None, "--agent-id", help="Comma-separated agent IDs"),
):
    """Run article generation (and optionally publish) for agents."""

    async def _run_batch():
        from agent_publisher.services.task_service import TaskService

        async with await _get_session() as session:
            task_svc = TaskService(session)

            if all_agents:
                console.print("[yellow]Running batch for all active agents...[/yellow]")
                task = await task_svc.run_batch_all()
                console.print(f"[green]Batch complete! Task={task.id} Status={task.status}[/green]")
                if task.result:
                    for r in task.result.get("results", []):
                        status_color = "green" if r.get("status") == "success" else "red"
                        console.print(f"  [{status_color}]{r}[/{status_color}]")
            elif agent_id:
                ids = [int(x.strip()) for x in agent_id.split(",")]
                for aid in ids:
                    console.print(f"[yellow]Generating for agent {aid}...[/yellow]")
                    task = await task_svc.run_generate(aid)
                    status_color = "green" if task.status == "success" else "red"
                    console.print(f"  [{status_color}]Task={task.id} {task.status}: {task.result}[/{status_color}]")
            else:
                console.print("[red]Specify --all or --agent-id[/red]")
                raise typer.Exit(1)

    _run(_run_batch())


# ==================== Task ====================

task_app = typer.Typer(help="Task management")
app.add_typer(task_app, name="task")


@task_app.command("list")
def task_list():
    """List recent tasks."""

    async def _list():
        from sqlalchemy import select

        from agent_publisher.models.task import Task

        async with await _get_session() as session:
            result = await session.execute(select(Task).order_by(Task.id.desc()).limit(20))
            tasks = result.scalars().all()
            table = Table(title="Tasks")
            table.add_column("ID", style="cyan")
            table.add_column("Agent")
            table.add_column("Type")
            table.add_column("Status")
            table.add_column("Started")
            table.add_column("Finished")
            for t in tasks:
                color = {"success": "green", "failed": "red", "running": "yellow"}.get(t.status, "")
                table.add_row(
                    str(t.id), str(t.agent_id or "-"), t.task_type,
                    f"[{color}]{t.status}[/{color}]" if color else t.status,
                    str(t.started_at or "-"), str(t.finished_at or "-"),
                )
            console.print(table)

    _run(_list())


@task_app.command("status")
def task_status(task_id: int = typer.Argument(..., help="Task ID")):
    """View task details."""

    async def _status():
        from agent_publisher.models.task import Task

        async with await _get_session() as session:
            task = await session.get(Task, task_id)
            if not task:
                console.print(f"[red]Task {task_id} not found[/red]")
                raise typer.Exit(1)
            console.print(f"[bold]Task {task.id}[/bold]")
            console.print(f"  Type: {task.task_type}")
            console.print(f"  Status: {task.status}")
            console.print(f"  Agent: {task.agent_id or 'N/A'}")
            console.print(f"  Started: {task.started_at or 'N/A'}")
            console.print(f"  Finished: {task.finished_at or 'N/A'}")
            if task.result:
                import json
                console.print(f"  Result: {json.dumps(task.result, ensure_ascii=False, indent=2)}")

    _run(_status())


# ==================== RSS ====================

rss_app = typer.Typer(help="RSS feed management")
app.add_typer(rss_app, name="rss")


@rss_app.command("test")
def rss_test(url: str = typer.Argument(..., help="RSS feed URL")):
    """Test if an RSS feed URL is accessible."""

    async def _test():
        from agent_publisher.services.rss_service import RSSService

        console.print(f"[yellow]Testing RSS feed: {url}[/yellow]")
        result = await RSSService.test_feed(url)
        if result["success"]:
            console.print(f"[green]Feed OK! {result['item_count']} items found[/green]")
            for title in result.get("sample_titles", []):
                console.print(f"  - {title}")
        else:
            console.print(f"[red]Feed failed: {result.get('error')}[/red]")

    _run(_test())


@rss_app.command("fetch")
def rss_fetch(agent_id: int = typer.Argument(..., help="Agent ID")):
    """Manually fetch RSS feeds for an agent."""

    async def _fetch():
        from agent_publisher.models.agent import Agent
        from agent_publisher.services.rss_service import RSSService

        async with await _get_session() as session:
            agent = await session.get(Agent, agent_id)
            if not agent:
                console.print(f"[red]Agent {agent_id} not found[/red]")
                raise typer.Exit(1)
            console.print(f"[yellow]Fetching RSS for agent '{agent.name}'...[/yellow]")
            items = await RSSService.fetch_agent_feeds(agent.rss_sources or [])
            console.print(f"[green]Found {len(items)} news items[/green]")
            for item in items[:10]:
                console.print(f"  [{item.source_name}] {item.title}")

    _run(_fetch())


# ==================== Setup Guide ====================

setup_app = typer.Typer(help="Setup guides and configuration helpers")
app.add_typer(setup_app, name="setup")


SETUP_GUIDE_TEXT = """
[bold cyan]━━━ 微信公众号快速配置指南 ━━━[/bold cyan]

[bold]第 1 步：注册公众号[/bold]
  访问 [link=https://mp.weixin.qq.com/cgi-bin/readtemplate?t=register/step1_tmpl&lang=zh_CN]https://mp.weixin.qq.com → 注册[/link]
  按照页面提示完成：基本信息 → 选择类型 → 信息登记 → 公众号信息
  [dim]个人推荐选「订阅号」（每天可群发1次），企业推荐「服务号」[/dim]

[bold]第 2 步：获取开发者密钥[/bold]
  登录 [link=https://developers.weixin.qq.com/console/product/mp]微信开发者平台[/link]
  左侧菜单选择「我的业务与服务」→「公众号」
  在「基础信息」页面找到：
    • [green]AppID[/green] — 直接复制
    • [green]AppSecret[/green] — 点击「重置」获取（[bold red]仅显示一次，立即保存！[/bold red]）

[bold]第 3 步：配置 IP 白名单[/bold]
  在「基础信息」页面找到「API IP白名单」，点击「编辑」
  将服务器的公网 IP 添加进去：
    [cyan]curl ifconfig.me[/cyan]  ← 运行此命令查看 IP
  [dim]家用宽带 IP 会变化，建议用固定 IP 的云服务器部署[/dim]

[bold]第 4 步：添加公众号到 Agent Publisher[/bold]
  [cyan]agent-pub account add --name "公众号名称" --appid "你的AppID" --appsecret "你的AppSecret"[/cyan]

[bold]第 5 步：创建 Agent[/bold]
  [cyan]agent-pub agent add --name "科技观察员" --topic "AI科技" --account-id 1 --rss "https://..."[/cyan]

[bold]第 6 步：生成并发布文章[/bold]
  [cyan]agent-pub article generate 1[/cyan]    ← 生成文章
  [cyan]agent-pub article preview 1[/cyan]     ← 预览内容
  [cyan]agent-pub article publish 1[/cyan]     ← 发布到草稿箱

[bold cyan]━━━ Skills API（AI Agent 接入） ━━━[/bold cyan]

如果你是通过 AI Agent（OpenClaw 等）接入，使用 Skills API：

  1. 认证：POST /api/skills/auth  {"email": "your@email.com"}
  2. 创建公众号：POST /api/skills/accounts
  3. 创建 Agent：POST /api/skills/agents
  4. 生成文章：POST /api/skills/agents/{id}/generate
  5. 查看文章：GET /api/skills/articles
  6. 发布文章：POST /api/skills/articles/{id}/publish

完整 API 文档：启动服务后访问 http://your-server:9099/docs
"""


@setup_app.command("guide")
def setup_guide():
    """Show the complete WeChat account setup guide (works in AI agent context)."""
    console.print(SETUP_GUIDE_TEXT)


@setup_app.command("check")
def setup_check():
    """Check current configuration status."""

    async def _check():
        from agent_publisher.config import settings as cfg

        table = Table(title="Configuration Status")
        table.add_column("Item", style="cyan")
        table.add_column("Status")
        table.add_column("Detail")

        # Database
        db_type = "PostgreSQL" if "postgresql" in cfg.database_url else "SQLite"
        table.add_row("Database", f"[green]{db_type}[/green]", cfg.database_url[:60] + "...")

        # Tencent Cloud
        tc_ok = bool(cfg.tencent_secret_id and cfg.tencent_secret_key)
        table.add_row(
            "Tencent Cloud",
            "[green]Configured[/green]" if tc_ok else "[red]Not configured[/red]",
            f"SecretID: {cfg.tencent_secret_id[:8]}..." if tc_ok else "Set TENCENT_SECRET_ID/KEY in .env",
        )

        # LLM
        llm_ok = bool(cfg.default_llm_api_key)
        table.add_row(
            "Default LLM",
            "[green]Configured[/green]" if llm_ok else "[yellow]Using default[/yellow]",
            f"{cfg.default_llm_provider}/{cfg.default_llm_model}",
        )

        # Email whitelist
        wl = cfg.get_email_whitelist()
        table.add_row(
            "Email Whitelist",
            f"[green]{len(wl)} emails[/green]" if wl else "[yellow]Empty[/yellow]",
            ", ".join(list(wl)[:3]) + ("..." if len(wl) > 3 else "") if wl else "Set EMAIL_WHITELIST in .env",
        )

        # Admins
        admins = cfg.get_admin_emails()
        table.add_row(
            "Admin Emails",
            f"[green]{len(admins)} admins[/green]" if admins else "[yellow]None[/yellow]",
            ", ".join(sorted(admins)[:3]) + ("..." if len(admins) > 3 else "") if admins else "Set ADMIN_EMAILS in .env",
        )

        # Accounts
        from sqlalchemy import select as sel, func
        from agent_publisher.models.account import Account

        async with await _get_session() as session:
            count = (await session.execute(sel(func.count(Account.id)))).scalar() or 0
            table.add_row(
                "WeChat Accounts",
                f"[green]{count} account(s)[/green]" if count else "[yellow]None[/yellow]",
                "Run: agent-pub account add ..." if not count else "",
            )

        console.print(table)

    _run(_check())


# ==================== Image ====================

image_app = typer.Typer(help="Image generation")
app.add_typer(image_app, name="image")


@image_app.command("generate")
def image_generate(prompt: str = typer.Argument(..., help="Image description")):
    """Test Hunyuan image generation."""

    async def _gen():
        from agent_publisher.services.image_service import HunyuanImageService

        svc = HunyuanImageService()
        console.print(f"[yellow]Generating image: {prompt}[/yellow]")
        try:
            result = await svc.generate_image(prompt)
            if result.startswith("http"):
                console.print(f"[green]Image URL: {result}[/green]")
            else:
                console.print(f"[green]Image generated (base64, {len(result)} chars)[/green]")
        except Exception as e:
            console.print(f"[red]Image generation failed: {e}[/red]")

    _run(_gen())


# ==================== Collect ====================

@app.command("collect")
def collect(
    agent_id: Optional[int] = typer.Option(None, "--agent-id", help="Agent ID to collect for"),
    all_agents: bool = typer.Option(False, "--all", help="Collect for all active agents"),
):
    """Collect trending/RSS/search materials for agents (no LLM required)."""

    async def _collect():
        from sqlalchemy import select

        from agent_publisher.models.agent import Agent
        from agent_publisher.services.source_registry_service import SourceRegistryService

        async with await _get_session() as session:
            registry_svc = SourceRegistryService(session)

            if all_agents:
                result = await session.execute(
                    select(Agent).where(Agent.is_active.is_(True)).order_by(Agent.id)
                )
                agents = result.scalars().all()
                if not agents:
                    console.print("[yellow]No active agents found[/yellow]")
                    raise typer.Exit(0)

                console.print(f"[yellow]Collecting for {len(agents)} active agent(s)...[/yellow]")
                grand_total = 0
                for agent in agents:
                    console.print(f"  [yellow]Agent {agent.id} ({agent.name})...[/yellow]", end="")
                    try:
                        collect_result = await registry_svc.collect_for_agent(agent)
                        total = sum(len(ids) for ids in collect_result.values())
                        grand_total += total
                        summary = ", ".join(f"{k}={len(v)}" for k, v in collect_result.items()) or "none"
                        console.print(f" [green]{total} materials ({summary})[/green]")
                    except Exception as e:
                        console.print(f" [red]failed: {e}[/red]")

                console.print(f"[green]Total collected: {grand_total} materials[/green]")

            elif agent_id is not None:
                agent = await session.get(Agent, agent_id)
                if not agent:
                    console.print(f"[red]Agent {agent_id} not found[/red]")
                    raise typer.Exit(1)

                console.print(f"[yellow]Collecting for agent '{agent.name}' (id={agent.id})...[/yellow]")
                collect_result = await registry_svc.collect_for_agent(agent)
                total = sum(len(ids) for ids in collect_result.values())
                summary = ", ".join(f"{k}={len(v)}" for k, v in collect_result.items()) or "none"
                console.print(f"[green]Collected {total} materials ({summary})[/green]")

            else:
                console.print("[red]Specify --agent-id or --all[/red]")
                raise typer.Exit(1)

    _run(_collect())


if __name__ == "__main__":
    app()
