"""Simulation routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models.project import Building
from app.models.simulation import SimulationConfig, SimulationRun, SimulationStatus, SimulationStrategy
from app.models.user import User
from app.schemas.api import SimulationProgressResponse, SimulationRunResponse, SimulationStart

router = APIRouter()

# City → EPW file mapping
_CITY_EPW: dict[str, str] = {
    "Seoul": "KOR_Seoul.Ws.108.epw",
    "Busan": "KOR_Busan.159.epw",
    "Daegu": "KOR_Daegu.143.epw",
    "Daejeon": "KOR_Daejeon.133.epw",
    "Gwangju": "KOR_Gwangju.156.epw",
    "Incheon": "KOR_Incheon.112.epw",
    "Gangneung": "KOR_Gangneung.105.epw",
    "Jeju": "KOR_Jeju.184.epw",
    "Cheongju": "KOR_Cheongju.131.epw",
    "Ulsan": "KOR_Ulsan.152.epw",
}


@router.post("", response_model=SimulationProgressResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_simulation(
    body: SimulationStart,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """POST /simulations - 시뮬레이션 시작."""
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

    # Determine strategies
    strategies = body.strategies or [s.value for s in SimulationStrategy]

    # Determine EPW file
    epw_file = _CITY_EPW.get(body.climate_city, "KOR_Seoul.Ws.108.epw")

    # Create config
    config = SimulationConfig(
        building_id=body.building_id,
        climate_city=body.climate_city,
        epw_file=epw_file,
        period_type=body.period_type,
        strategies=strategies,
    )
    db.add(config)
    await db.flush()

    # Create runs for each strategy
    runs = []
    for strategy_str in strategies:
        run = SimulationRun(
            config_id=config.id,
            strategy=SimulationStrategy(strategy_str),
            status=SimulationStatus.PENDING,
        )
        db.add(run)
        runs.append(run)
    await db.flush()

    # TODO: dispatch Celery tasks here
    # for run in runs:
    #     run_simulation_task.delay(str(run.id))

    return {
        "config_id": config.id,
        "total_strategies": len(strategies),
        "completed": 0,
        "running": 0,
        "failed": 0,
        "runs": [
            SimulationRunResponse.model_validate(r) for r in runs
        ],
        "estimated_remaining_seconds": len(strategies) * 300,  # rough estimate
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
        .options(selectinload(SimulationConfig.runs))
        .join(SimulationConfig.building)
        .where(SimulationConfig.id == config_id)
        .where(SimulationConfig.building.has(
            Building.project.has(user_id=user.id)
        ))
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
        .where(SimulationConfig.building.has(
            Building.project.has(user_id=user.id)
        ))
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    cancelled = 0
    for run in config.runs:
        if run.status in (SimulationStatus.PENDING, SimulationStatus.QUEUED, SimulationStatus.RUNNING):
            run.status = SimulationStatus.CANCELLED
            cancelled += 1

    await db.flush()
    return {"message": f"Cancelled {cancelled} runs"}
