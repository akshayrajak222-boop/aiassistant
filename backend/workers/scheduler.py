"""
workers/scheduler.py – Background job scheduler using APScheduler.
"""

from __future__ import annotations

import logging
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.workers.email_worker import run_email_check_job

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    """Initialize and start the background task scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        return scheduler

    scheduler = AsyncIOScheduler()

    # Read interval from env var, default 15 minutes
    try:
        poll_interval = int(os.environ.get("EMAIL_POLL_INTERVAL_MINUTES", "15"))
    except ValueError:
        poll_interval = 15

    scheduler.add_job(
        run_email_check_job,
        trigger=IntervalTrigger(minutes=poll_interval),
        id="email_inbox_monitor",
        name="Check inbox for new/urgent emails",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info(f"Background scheduler started. Email check interval: {poll_interval} minutes.")
    return scheduler


def stop_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped.")
