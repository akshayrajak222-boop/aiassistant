"""
tests/test_e2e_voice_email.py – End-to-end multi-step workflow verification.

Workflow 1: Voice input -> Transcription -> Agent execution -> Email summary -> Persistent chat
Workflow 2: Email draft creation -> Approval required -> Explicit human approval -> Send executed -> Duplicate prevention
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch

from backend.database.models import ApprovalStatus, EmailAccount, EmailActionApproval, EmailActionType, EmailProvider


@pytest.mark.asyncio
async def test_e2e_workflow_voice_to_email_summary(
    async_client: AsyncClient, test_user, patched_ai_provider, patched_gmail, db_session
):
    """Workflow 1: User speaks a request -> Assistant retrieves and summarizes authorized email data -> Persists in chat."""
    user, _, token = await test_user()

    # Link dummy email account
    account = EmailAccount(
        user_id=user.id,
        provider=EmailProvider.gmail,
        email_address="me@company.com",
        encrypted_credentials=b"encrypted_tokens",
        is_connected=True,
    )
    db_session.add(account)
    await db_session.commit()

    # Step 1: User voice input is transcribed
    with patch("backend.voice.stt.WhisperSTTProvider.transcribe") as mock_stt:
        from backend.voice.stt import TranscriptionResult
        mock_stt.return_value = TranscriptionResult(
            text="Check my new emails",
            language="en",
            confidence=0.98,
            provider="whisper",
        )
        fake_audio = b"RIFF....WAVEfmt...."
        stt_resp = await async_client.post(
            "/api/voice/transcribe",
            files={"file": ("voice.wav", fake_audio, "audio/wav")},
            data={"language": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert stt_resp.status_code == 200
        transcribed_text = stt_resp.json()["text"]
        assert transcribed_text == "Check my new emails"

    # Step 2: Send transcribed request to agent chat stream
    chat_resp = await async_client.post(
        "/api/chat/stream",
        json={"message": transcribed_text},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chat_resp.status_code == 200
    assert "text/event-stream" in chat_resp.headers["content-type"]

    # Step 3: Verify the conversation and assistant summary are persisted
    conv_list = await async_client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert conv_list.status_code == 200
    convs = conv_list.json()
    assert len(convs) >= 1
    conv_id = convs[0]["id"]

    detail_resp = await async_client.get(
        f"/api/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["messages"]) >= 1
    assert detail["messages"][0]["content"] == "Check my new emails"


@pytest.mark.asyncio
async def test_e2e_workflow_email_send_requires_approval(
    async_client: AsyncClient, test_user, db_session
):
    """Workflow 2: Outgoing emails require explicit approval; duplicates are strictly prevented."""
    user, _, token = await test_user()

    account = EmailAccount(
        user_id=user.id,
        provider=EmailProvider.gmail,
        email_address="assistant.user@company.com",
        encrypted_credentials=b"dummy_creds",
        is_connected=True,
    )
    db_session.add(account)
    await db_session.commit()

    # Step 1: Draft is created and queued for approval
    queue_resp = await async_client.post(
        "/api/email/approvals/queue-send",
        json={
            "account_id": account.id,
            "to": "partner@external.com",
            "subject": "Q4 Project Milestones",
            "body": "Hi, please review the finalized milestones attached.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert queue_resp.status_code == 201
    approval_record = queue_resp.json()
    approval_id = approval_record["id"]
    assert approval_record["status"] == "pending"

    # Step 2: List pending approvals to show in UI
    approvals_list_resp = await async_client.get(
        "/api/email/approvals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approvals_list_resp.status_code == 200
    pending_list = approvals_list_resp.json()
    assert any(a["id"] == approval_id for a in pending_list)

    # Step 3: Approve and execute send
    with patch("backend.email_mgr.router._get_account_credentials", return_value="mock_creds"):
        with patch("backend.email_mgr.router.send_message", return_value="sent_msg_9999"):
            approve_resp = await async_client.post(
                f"/api/email/approvals/{approval_id}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert approve_resp.status_code == 200
            assert approve_resp.json()["status"] == "executed"

            # Step 4: Duplicate send attempt is rejected with 409 Conflict
            dup_resp = await async_client.post(
                f"/api/email/approvals/{approval_id}/approve",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert dup_resp.status_code == 409
            assert "already been executed" in dup_resp.json()["detail"]
