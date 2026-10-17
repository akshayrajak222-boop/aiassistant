"""
main.py – Application entrypoint and lifecycle setup.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator
from dotenv import load_dotenv

# Load environment variables into os.environ
load_dotenv()
load_dotenv("../.env")

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agent.router import router as agent_router
from backend.api.health import router as health_router
from backend.api.settings import router as settings_router
from backend.auth.router import router as auth_router
from backend.config import get_settings
from backend.email_mgr.router import router as email_router
from backend.email_mgr.tools import configure_email_tools
from backend.memory.router import router as memory_router
from backend.tools.builtin import register_builtin_tools
from backend.voice.router import router as voice_router
from backend.workers.scheduler import start_scheduler, stop_scheduler

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager."""
    settings = get_settings()
    logger.info("application_startup", app_name=settings.app_name, env=settings.environment)

    # 0. Ensure database tables exist
    try:
        from backend.database.connection import get_engine
        from backend.database.models import Base
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_ensured")
    except Exception as exc:
        logger.warning("database_tables_init_failed", error=str(exc))

    # 1. Register default agent tools
    register_builtin_tools()

    # 2. Wire email tool dependencies
    try:
        from backend.database.connection import async_session_factory
        from backend.database.models import EmailAccount, EmailActionApproval, EmailActionType, ApprovalStatus
        from backend.email_mgr.oauth import get_credentials_from_encrypted
        from sqlalchemy import select

        async def _get_creds(user_id: str, account_id: str):
            async with async_session_factory() as db:
                stmt = select(EmailAccount).where(
                    EmailAccount.id == account_id,
                    EmailAccount.user_id == user_id,
                )
                res = await db.execute(stmt)
                acc = res.scalar_one_or_none()
                if not acc or not acc.encrypted_credentials:
                    raise ValueError(f"No credentials found for account {account_id}")
                return get_credentials_from_encrypted(acc.encrypted_credentials.decode("utf-8"))

        async def _create_approval(data: dict) -> str:
            async with async_session_factory() as db:
                appr = EmailActionApproval(
                    user_id=data["user_id"],
                    action_type=EmailActionType.send,
                    email_data=data,
                    status=ApprovalStatus.pending,
                )
                db.add(appr)
                await db.commit()
                await db.refresh(appr)
                return appr.id

        configure_email_tools(
            get_credentials_fn=_get_creds,
            get_ai_client_fn=lambda: None,
            create_approval_fn=_create_approval,
            get_db_session_fn=async_session_factory,
        )
    except Exception as exc:
        logger.warning("email_tools_wiring_skipped", error=str(exc))

    # 3. Start background job scheduler
    try:
        start_scheduler()
    except Exception as exc:
        logger.error("scheduler_startup_failed", error=str(exc))

    yield

    # Shutdown
    logger.info("application_shutdown")
    stop_scheduler()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="24/7 Personal AI Agent Platform inspired by Jarvis.",
        lifespan=lifespan,
    )

    # CORS configuration
    origins = [str(o).rstrip("/") for o in settings.cors_origins]
    for local_origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
        if local_origin not in origins:
            origins.append(local_origin)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )

    # Include API Routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(settings_router)
    app.include_router(agent_router)
    app.include_router(email_router)
    app.include_router(voice_router)
    app.include_router(memory_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
