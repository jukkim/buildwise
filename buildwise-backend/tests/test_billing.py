"""Billing endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_list_plans(client):
    resp = await client.get("/api/v1/billing/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    plans = {p["plan"] for p in data}
    assert plans == {"free", "pro", "enterprise"}

    free = next(p for p in data if p["plan"] == "free")
    assert free["price_monthly_usd"] == 0.0
    assert free["max_buildings"] == 3
    assert free["has_pdf_export"] is False

    pro = next(p for p in data if p["plan"] == "pro")
    assert pro["price_monthly_usd"] == 79.0
    assert pro["has_pdf_export"] is True


@pytest.mark.asyncio
async def test_get_usage(client):
    resp = await client.get("/api/v1/billing/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "free"
    assert data["simulations_used"] == 0
    assert data["simulations_limit"] == 5


@pytest.mark.asyncio
async def test_subscribe_not_implemented(client):
    resp = await client.post("/api/v1/billing/subscribe", json={"plan": "pro"})
    assert resp.status_code == 501
