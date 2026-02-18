"""Billing routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User, UserPlan
from app.schemas.api import PlanInfoResponse, UsageInfoResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# Static plan definitions
# ---------------------------------------------------------------------------
_PLANS: dict[str, dict] = {
    "free": {
        "plan": "free",
        "price_monthly_usd": 0.0,
        "max_buildings": 3,
        "max_simulations_monthly": 5,
        "allowed_strategies": ["baseline", "m0", "m1", "m2", "m3"],
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

    return {
        "plan": user.plan.value,
        "simulations_used": user.simulation_count_monthly,
        "simulations_limit": plan_info["max_simulations_monthly"],
        "buildings_count": 0,  # will be computed from DB
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
