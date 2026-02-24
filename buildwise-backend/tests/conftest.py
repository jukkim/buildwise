"""Shared test fixtures."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.db import get_db
from app.main import app
from app.models.user import User, UserPlan


def _make_user(**overrides) -> User:
    """Create a mock User ORM object."""
    defaults = {
        "id": uuid.uuid4(),
        "auth0_sub": "auth0|test123",
        "email": "test@buildwise.ai",
        "name": "Test User",
        "plan": UserPlan.FREE,
        "simulation_count_monthly": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


@pytest.fixture()
def test_user() -> User:
    return _make_user()


def _populate_db_defaults(obj):
    """Populate DB-generated fields on ORM objects (simulates flush + refresh)."""
    if hasattr(obj, "id") and obj.id is None:
        obj.id = uuid.uuid4()
    now = datetime.now(UTC)
    if hasattr(obj, "created_at") and obj.created_at is None:
        obj.created_at = now
    if hasattr(obj, "updated_at") and obj.updated_at is None:
        obj.updated_at = now
    if hasattr(obj, "status") and obj.status is None:
        obj.status = "active"


@pytest.fixture()
def mock_db():
    """Mock AsyncSession."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    async def _fake_flush(**kwargs):
        """Populate defaults on all added objects during flush."""
        if session.add.call_args_list:
            for call in session.add.call_args_list:
                obj = call.args[0] if call.args else None
                if obj is not None:
                    _populate_db_defaults(obj)

    async def _fake_refresh(obj, **kwargs):
        """Populate DB-generated fields on refresh."""
        _populate_db_defaults(obj)

    session.flush = AsyncMock(side_effect=_fake_flush)
    session.refresh = AsyncMock(side_effect=_fake_refresh)
    return session


@pytest.fixture()
async def client(test_user, mock_db) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with dependency overrides."""

    async def _override_db():
        yield mock_db

    async def _override_user():
        return test_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
