"""Shared API dependencies."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate Auth0 JWT, return the User row.

    MVP: reads ``X-User-Id`` header for local dev.
    Production: replace with Auth0 JWT verification.
    """
    # --- MVP dev shortcut ---
    user_id_header = request.headers.get("X-User-Id")
    if not user_id_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication",
        )

    try:
        user_id = uuid.UUID(user_id_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
