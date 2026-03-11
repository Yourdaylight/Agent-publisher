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
from agent_publisher.api.settings import router as settings_router
from agent_publisher.api.skills import router as skills_router, verify_skill_token
from agent_publisher.api.tasks import router as tasks_router
from agent_publisher.api.deps import get_db
from agent_publisher.config import settings
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: auto-create tables (for SQLite dev mode)
    if "sqlite" in settings.database_url:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite tables created/verified.")
    logger.info("Starting Agent Publisher scheduler...")
    await sync_agent_schedules()
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(title="Agent Publisher", version="0.1.0", lifespan=lifespan)

# Public routes (no auth required)
PUBLIC_PREFIXES = ("/api/auth/", "/api/skills/auth", "/assets/", "/favicon.ico")


@app.middleware("http")
async def auth_middleware(request: Request, call_next) -> Response:
    """Protect all /api/* routes except /api/auth/* with token verification."""
    path = request.url.path

    # Allow public paths, non-API paths (SPA), and SSE streams
    if not path.startswith("/api/") or any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    # Require Bearer token for all other API routes
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    token = auth_header[7:]

    # Skill endpoints accept skill tokens (email-based)
    if path.startswith("/api/skills/"):
        if not verify_skill_token(token):
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired skill token"})
        return await call_next(request)

    # All other API routes use the admin access_key token
    if not verify_token(token):
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    return await call_next(request)


app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(accounts_router)
app.include_router(agents_router)
app.include_router(articles_router)
app.include_router(tasks_router)
app.include_router(skills_router)


@app.get("/api/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    accounts = (await db.execute(select(func.count(Account.id)))).scalar() or 0
    agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
    articles = (await db.execute(select(func.count(Article.id)))).scalar() or 0
    tasks = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    return {"accounts": accounts, "agents": agents, "articles": articles, "tasks": tasks}


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
