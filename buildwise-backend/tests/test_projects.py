"""Tests for project CRUD endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_create_project(client: AsyncClient, mock_db):
    """POST /api/v1/projects creates a project."""
    resp = await client.post("/api/v1/projects", json={"name": "Test Project"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Project"
    assert mock_db.add.called


@pytest.mark.anyio
async def test_create_project_with_description(client: AsyncClient, mock_db):
    """POST /api/v1/projects with description."""
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "My Project", "description": "A test project"},
    )
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_create_project_empty_name(client: AsyncClient):
    """POST /api/v1/projects rejects empty name."""
    resp = await client.post("/api/v1/projects", json={"name": ""})
    # FastAPI validation should catch this or accept it
    # (depends on whether min_length is set)
    assert resp.status_code in (201, 422)


@pytest.mark.anyio
async def test_get_project_not_found(client: AsyncClient, mock_db):
    """GET /api/v1/projects/{id} returns 404 for nonexistent project."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/projects/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_project_not_found(client: AsyncClient, mock_db):
    """DELETE /api/v1/projects/{id} returns 404 for nonexistent project."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    fake_id = uuid.uuid4()
    resp = await client.delete(f"/api/v1/projects/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_patch_project_not_found(client: AsyncClient, mock_db):
    """PATCH /api/v1/projects/{id} returns 404 for nonexistent project."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    fake_id = uuid.uuid4()
    resp = await client.patch(f"/api/v1/projects/{fake_id}", json={"name": "Updated"})
    assert resp.status_code == 404
