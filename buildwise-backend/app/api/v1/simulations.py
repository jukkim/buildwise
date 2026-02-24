"""Simulation routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.api.v1.billing import _PLANS
from app.db import get_db
from app.models.project import Building
from app.models.simulation import SimulationConfig, SimulationStatus
from app.models.user import User
from app.schemas.api import (
    SimulationBatchResponse,
    SimulationProgressResponse,
    SimulationRunResponse,
    SimulationStart,
    SimulationStartBatch,
)
from app.services.simulation.service import (
    CITY_EPW_MAP,
    cancel_simulation_runs,
    create_simulation,
)

router = APIRouter()


@router.post("", response_model=SimulationProgressResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_simulation(
    body: SimulationStart,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /simulations - 시뮬레이션 시작."""
    # Monthly counter reset: if reset_at is in a previous month, reset counter
    now = datetime.now(UTC)
    if user.simulation_count_reset_at.month != now.month or user.simulation_count_reset_at.year != now.year:
        user.simulation_count_monthly = 0
        user.simulation_count_reset_at = now
        await db.flush()

    # Check monthly simulation quota (single source of truth from billing._PLANS)
    plan_info = _PLANS.get(user.plan.value, _PLANS["free"])
    plan_limit = plan_info["max_simulations_monthly"]
    if user.simulation_count_monthly >= plan_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly simulation limit reached ({plan_limit}). Upgrade your plan for more.",
        )

    # Verify building exists and belongs to user
    result = await db.execute(
        select(Building)
        .join(Building.project)
        .where(Building.id == body.building_id)
        .where(Building.project.has(user_id=user.id))
    )
    building = result.scalar_one_or_none()
    if building is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")

    # Validate climate city
    if body.climate_city not in CITY_EPW_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported climate city: {body.climate_city}. Supported: {list(CITY_EPW_MAP.keys())}",
        )

    # Filter strategies by plan allowance
    allowed = set(plan_info["allowed_strategies"])
    requested = body.strategies or []
    if requested:
        disallowed = [s for s in requested if s not in allowed]
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Strategies not available on your plan: {disallowed}",
            )

    # Delegate to service layer (handles strategy filtering via BPS validator)
    config = await create_simulation(
        db=db,
        building=building,
        climate_city=body.climate_city,
        period_type=body.period_type,
        requested_strategies=body.strategies,
    )

    # Atomic increment of monthly simulation counter (prevents race condition)
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(simulation_count_monthly=User.simulation_count_monthly + 1)
    )

    # Dispatch Celery task to run all strategies
    from app.tasks.simulation import dispatch_simulation

    dispatch_simulation.delay(str(config.id))

    return {
        "config_id": config.id,
        "total_strategies": len(config.runs),
        "completed": 0,
        "running": 0,
        "failed": 0,
        "runs": [SimulationRunResponse.model_validate(r) for r in config.runs],
        "estimated_remaining_seconds": len(config.runs) * 300,
    }


@router.post("/batch", response_model=SimulationBatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_simulation_batch(
    body: SimulationStartBatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /simulations/batch - 다중 도시 시뮬레이션 시작."""
    now = datetime.now(UTC)
    if user.simulation_count_reset_at.month != now.month or user.simulation_count_reset_at.year != now.year:
        user.simulation_count_monthly = 0
        user.simulation_count_reset_at = now
        await db.flush()

    # Check quota atomically for all cities
    plan_info = _PLANS.get(user.plan.value, _PLANS["free"])
    plan_limit = plan_info["max_simulations_monthly"]
    needed = len(body.climate_cities)
    if user.simulation_count_monthly + needed > plan_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Need {needed} simulation credits but only {plan_limit - user.simulation_count_monthly} remaining. Upgrade your plan.",
        )

    # Verify building exists and belongs to user
    result = await db.execute(
        select(Building)
        .join(Building.project)
        .where(Building.id == body.building_id)
        .where(Building.project.has(user_id=user.id))
    )
    building = result.scalar_one_or_none()
    if building is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")

    # Validate all cities
    for city in body.climate_cities:
        if city not in CITY_EPW_MAP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported climate city: {city}",
            )

    # Create N configs
    config_ids: list[uuid.UUID] = []
    for city in body.climate_cities:
        config = await create_simulation(
            db=db,
            building=building,
            climate_city=city,
            period_type=body.period_type,
        )
        config_ids.append(config.id)

    # Atomic increment counter for all N simulations
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(simulation_count_monthly=User.simulation_count_monthly + needed)
    )

    # Dispatch Celery tasks
    from app.tasks.simulation import dispatch_simulation

    for cid in config_ids:
        dispatch_simulation.delay(str(cid))

    return {
        "config_ids": config_ids,
        "total_configs": len(config_ids),
    }


@router.get("/{config_id}/progress", response_model=SimulationProgressResponse)
async def get_progress(
    config_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /simulations/{config_id}/progress - 진행 상황 조회."""
    result = await db.execute(
        select(SimulationConfig)
        .options(
            selectinload(SimulationConfig.runs),
            selectinload(SimulationConfig.building),
        )
        .join(SimulationConfig.building)
        .where(SimulationConfig.id == config_id)
        .where(SimulationConfig.building.has(Building.project.has(user_id=user.id)))
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    completed = sum(1 for r in config.runs if r.status == SimulationStatus.COMPLETED)
    running = sum(1 for r in config.runs if r.status == SimulationStatus.RUNNING)
    failed = sum(1 for r in config.runs if r.status == SimulationStatus.FAILED)
    remaining = len(config.runs) - completed - failed
    est_seconds = remaining * 300 if remaining > 0 else None

    return {
        "config_id": config.id,
        "building_id": config.building_id,
        "project_id": config.building.project_id if config.building else None,
        "building_name": config.building.name if config.building else None,
        "climate_city": config.climate_city,
        "total_strategies": len(config.runs),
        "completed": completed,
        "running": running,
        "failed": failed,
        "runs": [SimulationRunResponse.model_validate(r) for r in config.runs],
        "estimated_remaining_seconds": est_seconds,
    }


@router.post("/{config_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_simulation(
    config_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """POST /simulations/{config_id}/cancel - 시뮬레이션 취소."""
    result = await db.execute(
        select(SimulationConfig)
        .options(selectinload(SimulationConfig.runs))
        .join(SimulationConfig.building)
        .where(SimulationConfig.id == config_id)
        .where(SimulationConfig.building.has(Building.project.has(user_id=user.id)))
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # Delegate to service layer (handles status update + Celery revocation)
    cancelled = await cancel_simulation_runs(config)
    await db.flush()

    return {"message": f"Cancelled {cancelled} runs"}
