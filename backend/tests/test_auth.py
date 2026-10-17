"""
tests/test_auth.py – Authentication and access control test suite.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_valid_credentials(async_client: AsyncClient, test_user):
    user, password, _ = await test_user(email="login_valid@example.com", password="SecurePassword123!")

    resp = await async_client.post(
        "/api/auth/login",
        json={"email": "login_valid@example.com", "password": "SecurePassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in resp.cookies or "access_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, test_user):
    await test_user(email="wrong_pass@example.com", password="CorrectPassword123!")

    resp = await async_client.post(
        "/api/auth/login",
        json={"email": "wrong_pass@example.com", "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
    )
    # Generic error without revealing user existence
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_protected_route_without_token(async_client: AsyncClient):
    resp = await async_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_expired_token(async_client: AsyncClient, test_user):
    user, _, _ = await test_user()
    expired_token = pytest.make_expired_token(user.id)

    resp = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_session(async_client: AsyncClient, test_user):
    _, _, token = await test_user()

    resp = await async_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
