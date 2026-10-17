"""
email/router.py – FastAPI routes for email account connections, inbox browsing, and approval-based sending.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database.connection import get_db
from backend.database.models import (
    ApprovalStatus,
    AuditEvent,
    EmailAccount,
    EmailActionApproval,
    EmailActionType,
    EmailProvider,
    User,
)
from backend.email_mgr.gmail_client import get_message, list_messages, search_messages, send_message
from backend.email_mgr.oauth import (
    encrypt_credentials,
    exchange_code,
    get_auth_url,
    get_credentials_from_encrypted,
    revoke_credentials,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class EmailAccountResponse(BaseModel):
    id: str
    provider: str
    email_address: str
    is_connected: bool
    last_synced_at: str | None
    created_at: str


class OAuthStartResponse(BaseModel):
    authorization_url: str


class EmailMessageResponse(BaseModel):
    id: str
    thread_id: str
    subject: str
    from_email: str
    to_emails: list[str]
    date: str
    snippet: str
    is_read: bool
    labels: list[str]


class ApprovalResponse(BaseModel):
    id: str
    action_type: str
    email_data: dict[str, Any]
    status: str
    created_at: str
    decided_at: str | None


class DraftEmailRequest(BaseModel):
    account_id: str
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    reply_to_id: str | None = None


# ── Accounts & OAuth ─────────────────────────────────────────────────────────

@router.get("/accounts", response_model=list[EmailAccountResponse])
async def list_email_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List connected email accounts for current user."""
    stmt = select(EmailAccount).where(EmailAccount.user_id == current_user.id)
    res = await db.execute(stmt)
    accounts = res.scalars().all()
    return [
        EmailAccountResponse(
            id=acc.id,
            provider=acc.provider.value,
            email_address=acc.email_address,
            is_connected=acc.is_connected,
            last_synced_at=acc.last_synced_at.isoformat() if acc.last_synced_at else None,
            created_at=acc.created_at.isoformat(),
        )
        for acc in accounts
    ]


@router.post("/oauth/start", response_model=OAuthStartResponse)
async def start_oauth(
    enable_send: bool = Query(True),
    enable_modify: bool = Query(True),
    current_user: User = Depends(get_current_user),
):
    """Start Google OAuth flow to link a Gmail account."""
    auth_url = get_auth_url(
        user_id=current_user.id,
        enable_send=enable_send,
        enable_modify=enable_modify,
    )
    return OAuthStartResponse(authorization_url=auth_url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Process OAuth code exchange from Google."""
    try:
        credentials, user_id = exchange_code(code=code, state=state)
    except Exception as exc:
        logger.error(f"OAuth exchange failed: {exc}")
        raise HTTPException(status_code=400, detail=f"OAuth verification failed: {str(exc)}")

    email_addr = getattr(credentials, "email_address", "unknown@gmail.com")
    encrypted_bytes = encrypt_credentials(credentials).encode("utf-8")

    # Upsert email account
    stmt = select(EmailAccount).where(
        EmailAccount.user_id == user_id,
        EmailAccount.email_address == email_addr,
    )
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()

    if not account:
        account = EmailAccount(
            user_id=user_id,
            provider=EmailProvider.gmail,
            email_address=email_addr,
            encrypted_credentials=encrypted_bytes,
            scopes=list(credentials.scopes or []),
            is_connected=True,
            last_synced_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(account)
    else:
        account.encrypted_credentials = encrypted_bytes
        account.scopes = list(credentials.scopes or [])
        account.is_connected = True
        account.last_synced_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    return {"status": "success", "email_address": email_addr, "message": "Account connected successfully."}


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect and revoke credentials for an email account."""
    stmt = select(EmailAccount).where(
        EmailAccount.id == account_id,
        EmailAccount.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Email account not found.")

    if account.encrypted_credentials:
        try:
            revoke_credentials(account.encrypted_credentials.decode("utf-8"))
        except Exception:
            logger.warning("Revocation request failed; continuing to delete local record.")

    await db.delete(account)
    await db.commit()
    return None


# ── Inbox & Messages ─────────────────────────────────────────────────────────

async def _get_account_credentials(account_id: str, user_id: str, db: AsyncSession):
    stmt = select(EmailAccount).where(
        EmailAccount.id == account_id,
        EmailAccount.user_id == user_id,
        EmailAccount.is_connected == True,
    )
    res = await db.execute(stmt)
    acc = res.scalar_one_or_none()
    if not acc or not acc.encrypted_credentials:
        raise HTTPException(status_code=404, detail="Connected email account not found.")
    return get_credentials_from_encrypted(acc.encrypted_credentials.decode("utf-8"))


@router.get("/inbox", response_model=list[EmailMessageResponse])
async def get_inbox_messages(
    account_id: str = Query(...),
    max_results: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List inbox messages for a connected account."""
    creds = await _get_account_credentials(account_id, current_user.id, db)
    messages = list_messages(creds, query="in:inbox", max_results=max_results)
    return [
        EmailMessageResponse(
            id=m["id"],
            thread_id=m["thread_id"],
            subject=m["subject"],
            from_email=m["from_email"],
            to_emails=m["to_emails"],
            date=m["date"],
            snippet=m["snippet"],
            is_read=m["is_read"],
            labels=m["labels"],
        )
        for m in messages
    ]


@router.get("/messages/{message_id}")
async def get_message_detail(
    message_id: str,
    account_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full message content (sanitized for safe web display)."""
    creds = await _get_account_credentials(account_id, current_user.id, db)
    msg = get_message(creds, message_id)
    return msg


@router.get("/search", response_model=list[EmailMessageResponse])
async def search_inbox(
    q: str = Query(..., min_length=1),
    account_id: str = Query(...),
    max_results: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search messages using Gmail query syntax."""
    creds = await _get_account_credentials(account_id, current_user.id, db)
    messages = search_messages(creds, query=q, max_results=max_results)
    return [
        EmailMessageResponse(
            id=m["id"],
            thread_id=m["thread_id"],
            subject=m["subject"],
            from_email=m["from_email"],
            to_emails=m["to_emails"],
            date=m["date"],
            snippet=m["snippet"],
            is_read=m["is_read"],
            labels=m["labels"],
        )
        for m in messages
    ]


# ── Approvals & Sending ──────────────────────────────────────────────────────

@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    status_filter: ApprovalStatus | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pending or past email action approvals."""
    stmt = (
        select(EmailActionApproval)
        .where(EmailActionApproval.user_id == current_user.id)
        .order_by(desc(EmailActionApproval.created_at))
    )
    if status_filter:
        stmt = stmt.where(EmailActionApproval.status == status_filter)

    res = await db.execute(stmt)
    approvals = res.scalars().all()
    return [
        ApprovalResponse(
            id=a.id,
            action_type=a.action_type.value,
            email_data=a.email_data,
            status=a.status.value,
            created_at=a.created_at.isoformat(),
            decided_at=a.decided_at.isoformat() if a.decided_at else None,
        )
        for a in approvals
    ]


@router.post("/approvals/queue-send", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def queue_send_approval(
    req: DraftEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue an email for explicit user approval before sending."""
    approval = EmailActionApproval(
        user_id=current_user.id,
        action_type=EmailActionType.send,
        email_data={
            "account_id": req.account_id,
            "to": req.to,
            "subject": req.subject,
            "body": req.body,
            "reply_to_id": req.reply_to_id,
        },
        status=ApprovalStatus.pending,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return ApprovalResponse(
        id=approval.id,
        action_type=approval.action_type.value,
        email_data=approval.email_data,
        status=approval.status.value,
        created_at=approval.created_at.isoformat(),
        decided_at=None,
    )


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_and_execute(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve and execute a queued email action (e.g. sending).

    Enforces duplicate-send prevention: atomic status check ensures an email is never sent twice.
    """
    stmt = select(EmailActionApproval).where(
        EmailActionApproval.id == approval_id,
        EmailActionApproval.user_id == current_user.id,
    ).with_for_update()
    res = await db.execute(stmt)
    approval = res.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found.")

    if approval.status == ApprovalStatus.executed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email action has already been executed. Duplicate execution prevented.",
        )

    if approval.status != ApprovalStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve action in status '{approval.status.value}'.",
        )

    email_data = approval.email_data
    account_id = email_data.get("account_id")
    creds = await _get_account_credentials(account_id, current_user.id, db)

    try:
        # Actually execute sending via Gmail API
        sent_id = send_message(
            credentials=creds,
            to=email_data["to"],
            subject=email_data["subject"],
            body=email_data["body"],
            reply_to_id=email_data.get("reply_to_id"),
        )
        approval.status = ApprovalStatus.executed
        approval.decided_at = datetime.datetime.now(datetime.timezone.utc)
        approval.email_data["sent_message_id"] = sent_id

        # Audit event record
        audit = AuditEvent(
            user_id=current_user.id,
            event_type="email_sent",
            resource_type="email_action_approval",
            resource_id=approval.id,
            details={"to": email_data["to"], "subject": email_data["subject"], "message_id": sent_id},
        )
        db.add(audit)
        await db.commit()
        await db.refresh(approval)

        logger.info(f"Email sent successfully for approval {approval_id}")
        return ApprovalResponse(
            id=approval.id,
            action_type=approval.action_type.value,
            email_data=approval.email_data,
            status=approval.status.value,
            created_at=approval.created_at.isoformat(),
            decided_at=approval.decided_at.isoformat() if approval.decided_at else None,
        )
    except Exception as exc:
        logger.exception("Failed to send email during approved execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(exc)}",
        )


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_approval(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a queued email action."""
    stmt = select(EmailActionApproval).where(
        EmailActionApproval.id == approval_id,
        EmailActionApproval.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    approval = res.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found.")

    if approval.status != ApprovalStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject action in status '{approval.status.value}'.",
        )

    approval.status = ApprovalStatus.rejected
    approval.decided_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(approval)

    return ApprovalResponse(
        id=approval.id,
        action_type=approval.action_type.value,
        email_data=approval.email_data,
        status=approval.status.value,
        created_at=approval.created_at.isoformat(),
        decided_at=approval.decided_at.isoformat() if approval.decided_at else None,
    )
