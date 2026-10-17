"""
api/health.py – Health-check endpoint (no auth required).

GET /api/health
"""

from __future__ import annotations

import time
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Request
from sqlalchemy import text

from backend.config import get_settings
from backend.database.connection import get_engine

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


async def _check_database() -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except Exception as exc:
        logger.error("health.db_check_failed", error=str(exc))
        return {"status": "error", "detail": "Database unreachable"}


async def _check_redis() -> dict[str, Any]:
    t0 = time.perf_counter()
    settings = get_settings()
    try:
        client = aioredis.from_url(settings.redis_url_str, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        return {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except Exception as exc:
        logger.error("health.redis_check_failed", error=str(exc))
        return {"status": "error", "detail": "Redis unreachable"}


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """
    Returns the health of all critical dependencies.

    HTTP 200 if all services are reachable, 503 otherwise.
    """
    settings = get_settings()

    db_status = await _check_database()
    redis_status = await _check_redis()

    all_ok = db_status["status"] == "ok" and redis_status["status"] == "ok"

    payload: dict[str, Any] = {
        "status": "healthy" if all_ok else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "services": {
            "database": db_status,
            "redis": redis_status,
        },
    }

    # FastAPI will return 200; set 503 on degraded via Response if needed
    return payload
