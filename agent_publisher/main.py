from __future__ import annotations

import io
import logging
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from agent_publisher.version import get_version_info
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.accounts import router as accounts_router
from agent_publisher.api.agents import router as agents_router
from agent_publisher.api.groups import router as groups_router
from agent_publisher.api.llm_profiles import router as llm_profiles_router
from agent_publisher.api.articles import router as articles_router
from agent_publisher.api.auth import router as auth_router, verify_token
from agent_publisher.api.candidate_materials import router as candidate_materials_router
from agent_publisher.api.media import router as media_router
from agent_publisher.api.publish_records import router as publish_records_router
from agent_publisher.api.settings import router as settings_router
from agent_publisher.api.skills import router as skills_router, verify_skill_token
from agent_publisher.api.sources import router as sources_router
from agent_publisher.api.style_presets import router as style_presets_router
from agent_publisher.api.prompts import router as prompts_router
from agent_publisher.api.hotspots import router as hotspots_router
from agent_publisher.api.membership import router as membership_router
from agent_publisher.api.credits import router as credits_router
from agent_publisher.api.tasks import router as tasks_router
from agent_publisher.api.invite_codes import router as invite_codes_router
from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.config import settings
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.llm_profile import LLMProfile
from agent_publisher.models.media import MediaAsset
from agent_publisher.models.style_preset import StylePreset
from agent_publisher.models.prompt_template import PromptTemplate
from agent_publisher.models.membership_plan import MembershipPlan
from agent_publisher.models.user_membership import UserMembership
from agent_publisher.models.order import Order
from agent_publisher.models.task import Task
from agent_publisher.models.credits import CreditsBalance, CreditsTransaction  # noqa: F401
from agent_publisher.models.group import UserGroup, UserGroupMember  # noqa: F401 – ensure tables are created
from agent_publisher.models.invite_code import InviteCode, InviteRedemption  # noqa: F401
from agent_publisher.database import engine
from agent_publisher.models.base import Base
from agent_publisher.extensions import registry as extension_registry
from agent_publisher.api.extensions import router as extensions_router
from agent_publisher.scheduler import scheduler, sync_agent_schedules

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
SKILLS_DIR = Path(__file__).parent.parent / "skills"


async def _auto_migrate_sqlite(conn):
    """Auto-migrate SQLite: add missing columns to existing tables."""
    import sqlalchemy as sa

    def _do_migrate(sync_conn):
        inspector = sa.inspect(sync_conn)
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing_cols:
                    col_type = col.type.compile(sync_conn.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    default = ""
                    if col.default is not None and col.default.arg is not None:
                        dv = col.default.arg
                        if isinstance(dv, str):
                            default = f" DEFAULT '{dv}'"
                        elif isinstance(dv, bool):
                            default = f" DEFAULT {1 if dv else 0}"
                        elif isinstance(dv, (int, float)):
                            default = f" DEFAULT {dv}"
                    ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type} {nullable}{default}"
                    logger.info(f"Auto-migrate: {ddl}")
                    sync_conn.execute(sa.text(ddl))

        # Fix: make agents.account_id nullable if it's currently NOT NULL
        # SQLite cannot ALTER COLUMN, so we rebuild the table
        if inspector.has_table("agents"):
            cols = inspector.get_columns("agents")
            acct_col = next((c for c in cols if c["name"] == "account_id"), None)
            if acct_col and not acct_col.get("nullable", True):
                logger.info("Auto-migrate: rebuilding agents table to make account_id nullable")
                col_defs = []
                for c in cols:
                    col_type = str(c["type"])
                    name = c["name"]
                    nullable_part = "" if c.get("nullable", True) or name == "account_id" else " NOT NULL"
                    default_part = f" DEFAULT {c['default']}" if c.get("default") is not None else ""
                    pk = " PRIMARY KEY" if name == "id" else ""
                    col_defs.append(f"{name} {col_type}{pk}{nullable_part}{default_part}")
                col_list = ", ".join(col_defs)
                col_names = ", ".join(c["name"] for c in cols)
                sync_conn.execute(sa.text(f"ALTER TABLE agents RENAME TO _agents_old"))
                sync_conn.execute(sa.text(f"CREATE TABLE agents ({col_list})"))
                sync_conn.execute(sa.text(f"INSERT INTO agents ({col_names}) SELECT {col_names} FROM _agents_old"))
                sync_conn.execute(sa.text(f"DROP TABLE _agents_old"))

    await conn.run_sync(_do_migrate)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: auto-create tables (for SQLite dev mode)
    if "sqlite" in settings.database_url:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Auto-migrate: add any missing columns to existing tables
            await _auto_migrate_sqlite(conn)
        logger.info("SQLite tables created/verified (with auto-migration).")

    # Initialize built-in style presets / prompt templates / membership plans
    from agent_publisher.database import async_session_factory
    from agent_publisher.services.style_preset_service import StylePresetService
    from agent_publisher.services.prompt_template_service import PromptTemplateService
    from agent_publisher.services.membership_service import MembershipService
    async with async_session_factory() as session:
        sps = StylePresetService(session)
        await sps.init_builtin_presets()
        pts = PromptTemplateService(session)
        await pts.init_builtin_templates()
        ms = MembershipService(session)
        await ms.init_default_plans()

    # Initialize built-in agent(s)
    from agent_publisher.services.agent_init_service import init_builtin_agent
    async with async_session_factory() as session:
        await init_builtin_agent(session)

    # Seed default trending platform sources
    from agent_publisher.services.source_registry_service import SourceRegistryService
    async with async_session_factory() as session:
        registry = SourceRegistryService(session)
        seeded = await registry.seed_default_sources()
        if seeded:
            logger.info("Seeded %d default trending sources.", seeded)

    logger.info("Starting Agent Publisher scheduler...")
    await sync_agent_schedules()

    # Auto-install wenyan-cli if not found
    import shutil
    if not shutil.which('wenyan'):
        logger.info("wenyan-cli not found, attempting auto-install via npm...")
        import subprocess
        try:
            result = subprocess.run(
                ['npm', 'install', '-g', '@wenyan-md/cli'],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                logger.info("wenyan-cli installed successfully.")
            else:
                logger.warning("wenyan-cli install failed: %s", result.stderr[:500])
        except FileNotFoundError:
            logger.warning("npm not found — wenyan-cli auto-install skipped. Install Node.js to enable typesetting.")
        except subprocess.TimeoutExpired:
            logger.warning("wenyan-cli install timed out.")
        except Exception as e:
            logger.warning("wenyan-cli auto-install failed: %s", e)
    else:
        logger.info("wenyan-cli already available.")

    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(title="Agent Publisher", version=get_version_info()["version"], lifespan=lifespan)

# Public routes (no auth required)
# Note: auth endpoints are intentionally enumerated to keep `/api/auth/me`
# protected by the auth middleware.
PUBLIC_PREFIXES = (
    "/api/auth/login",
    "/api/auth/verify",
    "/api/auth/invite",
    "/api/version",
    "/api/skills/auth",
    "/api/skills/setup-guide",
    "/api/skill-package/",
    "/api/server-info",
    "/api/membership/plans",
    "/api/membership/contact",
    "/assets/",
    "/favicon.ico",
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next) -> Response:
    """Protect all /api/* routes except public paths with token verification.

    Token types:
      - Admin token: "{ts}.{sig}" (dot-separated, from access_key login)
      - Skill/email token: "{ts}|{email}|{sig}" (pipe-separated, from email login)

    After verification, the middleware injects user identity into request.state:
      - request.state.user_email: email string or "__admin__"
      - request.state.is_admin: bool
    """
    path = request.url.path

    # Allow public paths, non-API paths (SPA), and SSE streams
    if not path.startswith("/api/") or any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    # Allow media download without auth (public access for images)
    if path.startswith("/api/media/") and path.endswith("/download"):
        return await call_next(request)

    # Slideshow preview/download/subtitle support ?token= querystring auth (for iframe src)
    SLIDESHOW_TOKEN_PATHS = (
        "/api/extensions/slideshow/preview/",
        "/api/extensions/slideshow/chapter/",
        "/api/extensions/slideshow/timeline/",
        "/api/extensions/slideshow/status/",
        "/api/tasks/",  # SSE task streaming (EventSource can't send headers)
    )
    if any(path.startswith(p) for p in SLIDESHOW_TOKEN_PATHS):
        auth_header = request.headers.get("authorization", "")
        query_token = request.query_params.get("token", "")
        effective_token = (auth_header[7:] if auth_header.startswith("Bearer ") else None) or query_token
        if effective_token:
            # Validate and inject identity so route handler can use request.state
            if "|" in effective_token:
                email = verify_skill_token(effective_token)
                if email:
                    request.state.user_email = email
                    request.state.is_admin = settings.is_admin(email)
                    return await call_next(request)
            else:
                if verify_token(effective_token):
                    request.state.user_email = "__admin__"
                    request.state.is_admin = True
                    return await call_next(request)
        # Fall through to standard auth check below

    # Require Bearer token for all other API routes
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    token = auth_header[7:]

    # Determine token type by separator: "|" => skill/email token, "." => admin token
    if "|" in token:
        # Skill / email token
        email = verify_skill_token(token)
        if not email:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
        request.state.user_email = email
        request.state.is_admin = settings.is_admin(email)
    else:
        # Admin access_key token
        if not verify_token(token):
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
        request.state.user_email = "__admin__"
        request.state.is_admin = True

    return await call_next(request)


app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(accounts_router)
app.include_router(agents_router)
app.include_router(groups_router)
app.include_router(llm_profiles_router)
app.include_router(articles_router)
app.include_router(tasks_router)
app.include_router(media_router)
app.include_router(publish_records_router)
app.include_router(style_presets_router)
app.include_router(prompts_router)
app.include_router(hotspots_router)
app.include_router(membership_router)
app.include_router(credits_router)
app.include_router(skills_router)
app.include_router(sources_router)
app.include_router(candidate_materials_router)
app.include_router(extensions_router)
app.include_router(invite_codes_router)

# Discover and register extensions (graceful degradation: failures only logged)
extension_registry.discover_and_load()
extension_registry.register_all(app)


@app.get("/api/version")
async def version_info():
    """Public endpoint returning application version and git commit."""
    return get_version_info()


@app.get("/api/server-info")
async def server_info(request: Request):
    """Public endpoint returning server host for client-side display.

    Uses the configured server_host (domain or IP), or auto-detects.
    Falls back to the request's Host header if auto-detection returns loopback.
    """
    host = settings.get_server_host()
    # If auto-detect returned loopback, try to extract from the Host header
    if host in ("127.0.0.1", "0.0.0.0", "localhost", "::1"):
        host_header = request.headers.get("host", "")
        host_part = host_header.split(":")[0] if host_header else ""
        if host_part and host_part not in ("localhost", "127.0.0.1", "0.0.0.0"):
            host = host_part
    return {"server_host": host, "port": settings.port}


@app.get("/api/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    if user.is_admin:
        # Admin sees all data
        accounts = (await db.execute(select(func.count(Account.id)))).scalar() or 0
        agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
        articles = (await db.execute(select(func.count(Article.id)))).scalar() or 0
        tasks = (await db.execute(select(func.count(Task.id)))).scalar() or 0
        media = (await db.execute(select(func.count(MediaAsset.id)))).scalar() or 0
    else:
        # Normal user: filter by owner_email chain
        accounts = (await db.execute(
            select(func.count(Account.id)).where(Account.owner_email == user.email)
        )).scalar() or 0
        agents = (await db.execute(
            select(func.count(Agent.id)).join(Account).where(Account.owner_email == user.email)
        )).scalar() or 0
        articles = (await db.execute(
            select(func.count(Article.id)).join(Agent).join(Account).where(Account.owner_email == user.email)
        )).scalar() or 0
        tasks = (await db.execute(
            select(func.count(Task.id)).join(Agent).join(Account).where(Account.owner_email == user.email)
        )).scalar() or 0
        media = (await db.execute(
            select(func.count(MediaAsset.id)).where(MediaAsset.owner_email == user.email)
        )).scalar() or 0
    return {"accounts": accounts, "agents": agents, "articles": articles, "tasks": tasks, "media": media}


@app.get("/api/stats/source-modes")
async def source_mode_stats(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    from agent_publisher.services.governance_service import GovernanceService
    svc = GovernanceService(db)
    # Admin sees global stats; regular users see only their own
    owner_email = None if user.is_admin else user.email
    return await svc.get_source_mode_stats(owner_email=owner_email)


@app.get("/api/stats/tags")
async def tag_stats(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    from agent_publisher.services.governance_service import GovernanceService
    svc = GovernanceService(db)
    owner_email = None if user.is_admin else user.email
    return await svc.get_tag_stats(owner_email=owner_email)


@app.get("/api/stats/intake-trend")
async def intake_trend(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    from agent_publisher.services.governance_service import GovernanceService
    svc = GovernanceService(db)
    owner_email = None if user.is_admin else user.email
    return await svc.get_daily_intake_trend(days, owner_email=owner_email)


@app.get("/api/skill-package/download")
async def download_skill_package():
    """Package the skills/ directory as a zip for download."""
    if not SKILLS_DIR.is_dir():
        return JSONResponse(status_code=404, content={"detail": "Skills directory not found"})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in SKILLS_DIR.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                zf.write(f, f.relative_to(SKILLS_DIR))
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=agent-publisher-skill.zip"},
    )


# Serve static files (Vue build output) if the directory exists
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve Vue SPA – return index.html for any non-API, non-asset path.

        Security: resolve() + is_relative_to() prevents path traversal (LFI).
        """
        # Reject obvious traversal attempts early
        if ".." in full_path or full_path.startswith("/"):
            return FileResponse(STATIC_DIR / "index.html")

        file = (STATIC_DIR / full_path).resolve()
        static_root = STATIC_DIR.resolve()

        # Ensure resolved path stays within the static directory
        if file.is_relative_to(static_root) and file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        info = get_version_info()
        return {"name": "Agent Publisher", "version": info["version"], "commit": info["commit"]}


def start():
    """Entry point for `uvicorn agent_publisher.main:app`."""
    import uvicorn

    uvicorn.run(
        "agent_publisher.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    start()
