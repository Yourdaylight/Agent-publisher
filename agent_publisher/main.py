from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.accounts import router as accounts_router
from agent_publisher.api.agents import router as agents_router
from agent_publisher.api.articles import router as articles_router
from agent_publisher.api.auth import router as auth_router, verify_token
from agent_publisher.api.candidate_materials import router as candidate_materials_router
from agent_publisher.api.media import router as media_router
from agent_publisher.api.publish_records import router as publish_records_router
from agent_publisher.api.settings import router as settings_router
from agent_publisher.api.skills import router as skills_router, verify_skill_token
from agent_publisher.api.style_presets import router as style_presets_router
from agent_publisher.api.tasks import router as tasks_router
from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.config import settings
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.media import MediaAsset
from agent_publisher.models.style_preset import StylePreset
from agent_publisher.models.task import Task
from agent_publisher.database import engine
from agent_publisher.models.base import Base
from agent_publisher.scheduler import scheduler, sync_agent_schedules

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
GUIDE_IMAGES_DIR = Path(__file__).parent.parent / "docs" / "images"


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

    # Initialize built-in style presets
    from agent_publisher.database import async_session_factory
    from agent_publisher.services.style_preset_service import StylePresetService
    async with async_session_factory() as session:
        sps = StylePresetService(session)
        await sps.init_builtin_presets()

    logger.info("Starting Agent Publisher scheduler...")
    await sync_agent_schedules()
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(title="Agent Publisher", version="0.1.0", lifespan=lifespan)

# Public routes (no auth required)
PUBLIC_PREFIXES = ("/api/auth/", "/api/skills/auth", "/api/skills/setup-guide", "/assets/", "/favicon.ico")


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
app.include_router(articles_router)
app.include_router(tasks_router)
app.include_router(media_router)
app.include_router(publish_records_router)
app.include_router(style_presets_router)
app.include_router(skills_router)
app.include_router(candidate_materials_router)


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
async def source_mode_stats(db: AsyncSession = Depends(get_db)):
    from agent_publisher.services.governance_service import GovernanceService
    svc = GovernanceService(db)
    return await svc.get_source_mode_stats()


@app.get("/api/stats/tags")
async def tag_stats(db: AsyncSession = Depends(get_db)):
    from agent_publisher.services.governance_service import GovernanceService
    svc = GovernanceService(db)
    return await svc.get_tag_stats()


@app.get("/api/stats/intake-trend")
async def intake_trend(days: int = 30, db: AsyncSession = Depends(get_db)):
    from agent_publisher.services.governance_service import GovernanceService
    svc = GovernanceService(db)
    return await svc.get_daily_intake_trend(days)


# Serve guide images (setup screenshots) from docs/images/
if GUIDE_IMAGES_DIR.is_dir():
    app.mount("/guide-images", StaticFiles(directory=GUIDE_IMAGES_DIR), name="guide-images")

# Serve static files (Vue build output) if the directory exists
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve Vue SPA – return index.html for any non-API, non-asset path."""
        file = STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        return {"name": "Agent Publisher", "version": "0.1.0"}


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
