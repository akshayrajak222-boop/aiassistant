"""
database/connection.py – Async SQLAlchemy engine, session factory, and FastAPI dependency.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings

logger = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    url = settings.database_url_str
    if "sqlite" in url:
        return create_async_engine(
            url,
            echo=settings.debug,
            future=True,
        )
    return create_async_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,          # Detect stale connections
        echo=settings.debug,         # Log SQL only in debug mode
        future=True,
    )


def get_engine() -> AsyncEngine:
    """Return the module-level engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def async_session_factory() -> AsyncSession:
    """Convenience callable returning a new async session."""
    factory = get_session_factory()
    return factory()



async def init_db() -> None:
    """Called on application startup – verifies connectivity."""
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("database.connected")
    except Exception as exc:
        logger.error("database.connection_failed", error=str(exc))
        raise


async def close_db() -> None:
    """Called on application shutdown – disposes the connection pool."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("database.pool_disposed")
        _engine = None


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Async context-manager session (useful outside of FastAPI DI)."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# FastAPI dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
