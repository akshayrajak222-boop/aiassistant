"""
tests/test_memory.py – Persistent memory creation, retrieval, search, and user isolation.
"""

import pytest
from httpx import AsyncClient

from backend.database.models import MemoryEntryType
from backend.memory.service import memory_service


@pytest.mark.asyncio
async def test_memory_add_and_list(async_client: AsyncClient, test_user, db_session):
    user, _, token = await test_user()

    # Add memory via API
    resp = await async_client.post(
        "/api/memory",
        json={
            "content": "User prefers concise bullet points for meeting notes.",
            "entry_type": "preference",
            "tags": ["formatting", "meetings"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["content"] == "User prefers concise bullet points for meeting notes."
    assert created["entry_type"] == "preference"

    # List memories
    list_resp = await async_client.get(
        "/api/memory",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    entries = list_resp.json()
    assert len(entries) >= 1
    assert any(e["id"] == created["id"] for e in entries)


@pytest.mark.asyncio
async def test_memory_search(db_session, test_user):
    user, _, _ = await test_user()

    await memory_service.add_memory(
        db_session,
        user_id=user.id,
        content="Project Apollo deadline is November 15th.",
        entry_type=MemoryEntryType.fact,
        tags=["apollo", "deadlines"],
    )
    await memory_service.add_memory(
        db_session,
        user_id=user.id,
        content="Prefers dark roast coffee.",
        entry_type=MemoryEntryType.preference,
        tags=["coffee"],
    )

    # Search for Apollo
    results = await memory_service.search_memory(db_session, user_id=user.id, query="When is Apollo due?")
    assert len(results) > 0
    assert "November 15th" in results[0].content


@pytest.mark.asyncio
async def test_memory_user_isolation(async_client: AsyncClient, test_user, db_session):
    user1, _, token1 = await test_user(email="user1_mem@example.com")
    user2, _, token2 = await test_user(email="user2_mem@example.com")

    # User 1 creates memory
    m1 = await memory_service.add_memory(
        db_session,
        user_id=user1.id,
        content="Secret project codename is Zephyr.",
        entry_type=MemoryEntryType.fact,
    )

    # User 2 lists memories
    list_resp = await async_client.get(
        "/api/memory",
        headers={"Authorization": f"Bearer {token2}"},
    )
    entries = list_resp.json()
    assert not any(e["id"] == m1.id for e in entries)

    # User 2 tries to delete user 1's memory
    del_resp = await async_client.delete(
        f"/api/memory/{m1.id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert del_resp.status_code == 404
