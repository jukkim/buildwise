"""Auth endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_get_me(client, test_user):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@buildwise.ai"
    assert data["plan"] == "free"
    assert data["simulation_count_monthly"] == 0
