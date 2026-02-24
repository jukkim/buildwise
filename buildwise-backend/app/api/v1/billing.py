"""Billing routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.db import get_db
from app.models.project import Building, Project, ProjectStatus
from app.models.user import User
from app.schemas.api import PlanInfoResponse, UsageInfoResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Static plan definitions
# ---------------------------------------------------------------------------
_PLANS: dict[str, dict] = {
    "free": {
        "plan": "free",
        "price_monthly_usd": 0.0,
        "max_buildings": 50,
        "max_simulations_monthly": 500,
        "allowed_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"],
        "has_pdf_export": False,
    },
    "pro": {
        "plan": "pro",
        "price_monthly_usd": 79.0,
        "max_buildings": 20,
        "max_simulations_monthly": 50,
        "allowed_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"],
        "has_pdf_export": True,
    },
    "enterprise": {
        "plan": "enterprise",
        "price_monthly_usd": 0.0,  # custom pricing
        "max_buildings": 999,
        "max_simulations_monthly": 999,
        "allowed_strategies": ["baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"],
        "has_pdf_export": True,
    },
}


@router.get("/plans", response_model=list[PlanInfoResponse])
async def list_plans() -> list[dict]:
    """GET /billing/plans - 요금제 목록 (인증 불필요)."""
    return list(_PLANS.values())


@router.get("/usage", response_model=UsageInfoResponse)
async def get_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /billing/usage - 현재 사용량."""
    plan_info = _PLANS.get(user.plan.value, _PLANS["free"])

    # Count actual buildings across active projects
    result = await db.execute(
        select(func.count(Building.id))
        .join(Building.project)
        .where(Project.user_id == user.id)
        .where(Project.status != ProjectStatus.DELETED)
    )
    buildings_count = result.scalar() or 0

    return {
        "plan": user.plan.value,
        "simulations_used": user.simulation_count_monthly,
        "simulations_limit": plan_info["max_simulations_monthly"],
        "buildings_count": buildings_count,
        "buildings_limit": plan_info["max_buildings"],
        "credits_remaining": max(0, plan_info["max_simulations_monthly"] - user.simulation_count_monthly),
    }


@router.post("/subscribe")
async def subscribe(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """POST /billing/subscribe - 구독/업그레이드.

    MVP placeholder: Stripe integration will be added later.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Stripe integration not yet available",
    )
