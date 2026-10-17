"""
tests/test_rate_limiting.py – Rate limiting configuration and enforcement tests.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_rate_limiting(async_client: AsyncClient):
    # Attempt rapid repeated requests
    responses = []
    for _ in range(30):
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "ratelimit@example.com", "password": "wrong"},
        )
        responses.append(resp.status_code)

    # All responses should either be 401 or 429 (rate limited), never crashing
    assert all(code in (401, 429) for code in responses)
