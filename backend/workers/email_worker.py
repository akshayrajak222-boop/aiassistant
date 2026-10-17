"""
workers/email_worker.py – Scheduled background email monitor and notifier.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import async_session_factory
from backend.database.models import EmailAccount, ScheduledTask, TaskExecution, TaskExecutionStatus
from backend.email_mgr.gmail_client import list_messages
from backend.email_mgr.oauth import get_credentials_from_encrypted

logger = logging.getLogger(__name__)


class EmailMonitorWorker:
    """Worker that periodically monitors linked Gmail accounts for new or urgent messages."""

    async def check_all_accounts(self) -> dict[str, Any]:
        """Poll all connected email accounts and process unread messages."""
        logger.info("Starting scheduled email check...")
        results = {"accounts_checked": 0, "unread_found": 0, "errors": []}

        async with async_session_factory() as db:
            stmt = select(EmailAccount).where(EmailAccount.is_connected == True)
            res = await db.execute(stmt)
            accounts = res.scalars().all()

            for acc in accounts:
                if not acc.encrypted_credentials:
                    continue

                results["accounts_checked"] += 1
                try:
                    creds = get_credentials_from_encrypted(acc.encrypted_credentials.decode("utf-8"))
                    # Query unread messages
                    unread = list_messages(creds, query="is:unread in:inbox", max_results=10)
                    results["unread_found"] += len(unread)

                    # Update last sync timestamp
                    acc.last_synced_at = datetime.datetime.now(datetime.timezone.utc)
                    await db.commit()

                    if unread:
                        logger.info(
                            f"Account {acc.email_address}: found {len(unread)} unread message(s)."
                        )
                except Exception as exc:
                    err_msg = f"Failed checking account {acc.email_address}: {str(exc)}"
                    logger.warning(err_msg)
                    results["errors"].append(err_msg)

        logger.info(f"Finished email check: {results}")
        return results


email_worker = EmailMonitorWorker()


async def run_email_check_job() -> None:
    """Target function invoked by the background scheduler."""
    try:
        await email_worker.check_all_accounts()
    except Exception as exc:
        logger.exception(f"Unhandled error in email check job: {exc}")
