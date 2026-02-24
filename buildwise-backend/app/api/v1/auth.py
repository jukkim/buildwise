"""Auth routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.db import get_db
from app.models.user import User
from app.schemas.api import UserResponse

router = APIRouter()


class LoginRequest(BaseModel):
    email: str  # TODO: migrate to pydantic EmailStr after adding email-validator dep


class AuthConfigResponse(BaseModel):
    auth0_enabled: bool
    auth0_domain: str | None = None
    auth0_client_id: str | None = None
    auth0_audience: str | None = None


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config() -> dict:
    """GET /auth/config - Auth0 configuration for frontend.

    Returns Auth0 domain/client_id if configured, else signals dev mode.
    No authentication required (frontend needs this before login).
    """
    if settings.auth0_domain and settings.auth0_client_id:
        return {
            "auth0_enabled": True,
            "auth0_domain": settings.auth0_domain,
            "auth0_client_id": settings.auth0_client_id,
            "auth0_audience": settings.auth0_api_audience or None,
        }
    return {"auth0_enabled": False}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    """GET /auth/me - 현재 사용자 정보."""
    return user


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> User:
    """POST /auth/login - MVP dev login by email lookup.

    Only available in debug mode when Auth0 is not configured.
    """
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev login disabled in production.",
        )

    if settings.auth0_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dev login disabled. Use Auth0 authentication.",
        )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Run 'make seed' to create the demo user.",
        )
    return user
