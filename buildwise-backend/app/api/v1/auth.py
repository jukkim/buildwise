"""Auth routes."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.api import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    """GET /auth/me - 현재 사용자 정보."""
    return user
