"""Shared test fixtures."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
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
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


@pytest.fixture()
def test_user() -> User:
    return _make_user()


@pytest.fixture()
def mock_db():
    """Mock AsyncSession."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
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
