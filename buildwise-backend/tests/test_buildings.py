"""Tests for building endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.models.project import Building, Project, ProjectStatus


def _make_project(user_id: uuid.UUID) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = uuid.uuid4()
    project.user_id = user_id
    project.status = ProjectStatus.ACTIVE
    return project


@pytest.mark.anyio
async def test_list_buildings_project_not_found(client: AsyncClient, mock_db):
    """GET /api/v1/projects/{id}/buildings returns 404 for bad project."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/projects/{fake_id}/buildings")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_building_not_found(client: AsyncClient, mock_db, test_user):
    """GET /api/v1/projects/{pid}/buildings/{bid} returns 404."""
    project = _make_project(test_user.id)

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # First call: _get_project_or_404
            result.scalar_one_or_none.return_value = project
        else:
            # Second call: _get_building_or_404
            result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = mock_execute

    resp = await client.get(
        f"/api/v1/projects/{project.id}/buildings/{uuid.uuid4()}"
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_building_not_found(client: AsyncClient, mock_db, test_user):
    """DELETE /api/v1/projects/{pid}/buildings/{bid} returns 404."""
    project = _make_project(test_user.id)

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = project
        else:
            result.scalar_one_or_none.return_value = None
        return result

    mock_db.execute = mock_execute

    resp = await client.delete(
        f"/api/v1/projects/{project.id}/buildings/{uuid.uuid4()}"
    )
    assert resp.status_code == 404
