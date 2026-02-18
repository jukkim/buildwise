"""Building template endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_list_templates(client):
    resp = await client.get("/api/v1/buildings/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 6

    types = {t["building_type"] for t in data}
    assert types == {
        "large_office", "medium_office", "small_office",
        "standalone_retail", "primary_school", "hospital",
    }


@pytest.mark.asyncio
async def test_get_template_large_office(client):
    resp = await client.get("/api/v1/buildings/templates/large_office")
    assert resp.status_code == 200
    data = resp.json()
    assert data["building_type"] == "large_office"
    assert data["name"] == "Large Office"
    assert "default_bps" in data
    assert data["default_bps"]["hvac"]["system_type"] == "vav_chiller_boiler"
    assert "baseline" in data["available_strategies"]


@pytest.mark.asyncio
async def test_get_template_not_found(client):
    resp = await client.get("/api/v1/buildings/templates/unknown_type")
    assert resp.status_code == 404
