"""Result routes."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models.project import Building
from app.models.simulation import (
    EnergyResult,
    SimulationConfig,
    SimulationRun,
    SimulationStatus,
)
from app.models.user import User
from app.schemas.api import (
    EnergyResultResponse,
    StrategyComparisonResponse,
    TimeSeriesPoint,
    TimeSeriesResponse,
)

router = APIRouter()


@router.get("/{config_id}/results", response_model=StrategyComparisonResponse)
async def get_results(
    config_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /simulations/{config_id}/results - 전략 비교 결과."""
    result = await db.execute(
        select(SimulationConfig)
        .options(
            selectinload(SimulationConfig.runs).selectinload(SimulationRun.energy_result),
            selectinload(SimulationConfig.building),
        )
        .join(SimulationConfig.building)
        .where(SimulationConfig.id == config_id)
        .where(SimulationConfig.building.has(
            Building.project.has(user_id=user.id)
        ))
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    completed_runs = [r for r in config.runs if r.status == SimulationStatus.COMPLETED and r.energy_result]
    if not completed_runs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No completed results yet")

    baseline_result = None
    strategy_results = []

    for run in completed_runs:
        er = run.energy_result
        entry = EnergyResultResponse(
            strategy=run.strategy.value,
            total_energy_kwh=er.total_energy_kwh,
            hvac_energy_kwh=er.hvac_energy_kwh,
            cooling_energy_kwh=er.cooling_energy_kwh,
            heating_energy_kwh=er.heating_energy_kwh,
            fan_energy_kwh=er.fan_energy_kwh,
            eui_kwh_m2=er.eui_kwh_m2,
            peak_demand_kw=er.peak_demand_kw,
            savings_pct=er.savings_pct,
            annual_cost_krw=er.annual_cost_krw,
            annual_savings_krw=er.annual_savings_krw,
        )
        if run.strategy.value == "baseline":
            baseline_result = entry
        else:
            strategy_results.append(entry)

    # Simple recommendation: strategy with highest savings_pct
    recommended = None
    reason = None
    if strategy_results:
        best = max(
            (s for s in strategy_results if s.savings_pct is not None),
            key=lambda s: s.savings_pct or 0,
            default=None,
        )
        if best and best.savings_pct and best.savings_pct > 0:
            recommended = best.strategy
            reason = f"{best.savings_pct:.1f}% energy savings vs baseline"

    return {
        "building_name": config.building.name,
        "building_type": config.building.building_type.value,
        "climate_city": config.climate_city,
        "baseline": baseline_result,
        "strategies": strategy_results,
        "recommended_strategy": recommended,
        "recommendation_reason": reason,
    }


@router.get("/{config_id}/results/timeseries", response_model=list[TimeSeriesResponse])
async def get_timeseries(
    config_id: uuid.UUID,
    strategies: str | None = Query(None, description="Comma-separated strategies"),
    variables: str | None = Query(None, description="Comma-separated variables"),
    resolution: str = Query("monthly", enum=["hourly", "daily", "monthly"]),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """GET /simulations/{config_id}/results/timeseries - 시계열 데이터.

    MVP placeholder: returns empty data.
    Full implementation requires TimescaleDB hypertable queries.
    """
    # Verify access
    result = await db.execute(
        select(SimulationConfig)
        .join(SimulationConfig.building)
        .where(SimulationConfig.id == config_id)
        .where(SimulationConfig.building.has(
            Building.project.has(user_id=user.id)
        ))
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    # MVP: return empty structure
    strategy_list = strategies.split(",") if strategies else config.strategies
    variable_list = variables.split(",") if variables else ["total_energy"]

    results = []
    for strat in strategy_list:
        for var in variable_list:
            results.append({
                "strategy": strat,
                "variable": var,
                "resolution": resolution,
                "data": [],  # TimescaleDB query would go here
            })

    return results
