"""
tests/test_email.py – Email OAuth, inbox searching, draft creation, and approval-based sending.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from backend.database.models import ApprovalStatus, EmailAccount, EmailActionApproval, EmailActionType, EmailProvider


@pytest.mark.asyncio
async def test_oauth_start(async_client: AsyncClient, test_user):
    user, _, token = await test_user()

    with patch("backend.email_mgr.router.get_auth_url", return_value="https://accounts.google.com/o/oauth2/auth?test=1"):
        resp = await async_client.post(
            "/api/email/oauth/start",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "authorization_url" in resp.json()


@pytest.mark.asyncio
async def test_queue_and_approve_email_send(async_client: AsyncClient, test_user, db_session):
    user, _, token = await test_user()

    # Create dummy connected email account
    account = EmailAccount(
        user_id=user.id,
        provider=EmailProvider.gmail,
        email_address="sender@example.com",
        encrypted_credentials=b"dummy_encrypted_bytes",
        is_connected=True,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    # 1. Queue send approval
    queue_resp = await async_client.post(
        "/api/email/approvals/queue-send",
        json={
            "account_id": account.id,
            "to": "client@example.com",
            "subject": "Proposal Update",
            "body": "Here is the proposal we discussed.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert queue_resp.status_code == 201
    approval_data = queue_resp.json()
    assert approval_data["status"] == "pending"
    approval_id = approval_data["id"]

    # 2. Approve and execute (mocking send_message)
    with patch("backend.email_mgr.router._get_account_credentials", return_value="mock_creds"):
        with patch("backend.email_mgr.router.send_message", return_value="msg_sent_123"):
            approve_resp = await async_client.post(
                f"/api/email/approvals/{approval_id}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert approve_resp.status_code == 200
            data = approve_resp.json()
            assert data["status"] == "executed"
            assert data["email_data"]["sent_message_id"] == "msg_sent_123"

            # 3. Duplicate send prevention check: approving again must return 409 Conflict
            dup_resp = await async_client.post(
                f"/api/email/approvals/{approval_id}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert dup_resp.status_code == 409
            assert "Duplicate execution prevented" in dup_resp.json()["detail"]


@pytest.mark.asyncio
async def test_reject_email_approval(async_client: AsyncClient, test_user, db_session):
    user, _, token = await test_user()

    approval = EmailActionApproval(
        user_id=user.id,
        action_type=EmailActionType.send,
        email_data={"to": "client@example.com", "subject": "Test", "body": "Body"},
        status=ApprovalStatus.pending,
    )
    db_session.add(approval)
    await db_session.commit()
    await db_session.refresh(approval)

    reject_resp = await async_client.post(
        f"/api/email/approvals/{approval.id}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"
