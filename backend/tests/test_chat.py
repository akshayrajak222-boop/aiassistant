"""
tests/test_chat.py – Conversations, SSE streaming, and chat persistence tests.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_conversations(async_client: AsyncClient, test_user):
    user, _, token = await test_user()

    # Create conversation
    resp = await async_client.post(
        "/api/conversations",
        json={"title": "Test Chat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Chat"
    conv_id = data["id"]

    # List conversations
    list_resp = await async_client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    convs = list_resp.json()
    assert any(c["id"] == conv_id for c in convs)


@pytest.mark.asyncio
async def test_chat_stream_saves_messages(async_client: AsyncClient, test_user, patched_ai_provider):
    user, _, token = await test_user()

    # Create conversation
    conv_resp = await async_client.post(
        "/api/conversations",
        json={"title": "Stream Chat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    conv_id = conv_resp.json()["id"]

    # Send message to stream endpoint
    stream_resp = await async_client.post(
        "/api/chat/stream",
        json={"conversation_id": conv_id, "message": "Hello Jarvis!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers["content-type"]

    body = stream_resp.text
    assert "conversation_id" in body

    # Verify conversation persists with messages
    detail_resp = await async_client.get(
        f"/api/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["messages"]) >= 1
    assert detail["messages"][0]["content"] == "Hello Jarvis!"


@pytest.mark.asyncio
async def test_unauthorized_conversation_access(async_client: AsyncClient, test_user):
    user1, _, token1 = await test_user(email="user1@example.com")
    user2, _, token2 = await test_user(email="user2@example.com")

    # User 1 creates conversation
    conv_resp = await async_client.post(
        "/api/conversations",
        json={"title": "Private Chat"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    conv_id = conv_resp.json()["id"]

    # User 2 tries to access user 1's conversation
    forbidden_resp = await async_client.get(
        f"/api/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert forbidden_resp.status_code == 404
