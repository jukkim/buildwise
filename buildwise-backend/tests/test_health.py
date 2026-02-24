"""Health endpoint tests."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "buildwise-api"
    # version is only included in debug mode
    if os.environ.get("DEBUG", "").lower() in ("true", "1"):
        assert data["version"] == "0.1.0"
