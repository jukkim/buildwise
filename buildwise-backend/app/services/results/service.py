"""Result aggregation service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.simulation import (
    SimulationConfig,
    SimulationRun,
    SimulationStatus,
)


async def get_strategy_comparison(
    db: AsyncSession,
    config_id: uuid.UUID,
) -> dict | None:
    """Build strategy comparison response from completed runs."""
    result = await db.execute(
        select(SimulationConfig)
        .options(
            selectinload(SimulationConfig.runs).selectinload(SimulationRun.energy_result),
            selectinload(SimulationConfig.building),
        )
        .where(SimulationConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        return None

    completed = [r for r in config.runs if r.status == SimulationStatus.COMPLETED and r.energy_result is not None]
    if not completed:
        return None

    baseline = None
    strategies = []

    for run in completed:
        er = run.energy_result
        entry = {
            "strategy": run.strategy.value,
            "total_energy_kwh": er.total_energy_kwh,
            "hvac_energy_kwh": er.hvac_energy_kwh,
            "cooling_energy_kwh": er.cooling_energy_kwh,
            "heating_energy_kwh": er.heating_energy_kwh,
            "fan_energy_kwh": er.fan_energy_kwh,
            "eui_kwh_m2": er.eui_kwh_m2,
            "peak_demand_kw": er.peak_demand_kw,
            "savings_pct": er.savings_pct,
            "annual_cost_krw": er.annual_cost_krw,
            "annual_savings_krw": er.annual_savings_krw,
        }
        if run.strategy.value == "baseline":
            baseline = entry
        else:
            strategies.append(entry)

    # Recommendation: highest savings
    recommended = None
    reason = None
    valid = [s for s in strategies if s["savings_pct"] is not None and s["savings_pct"] > 0]
    if valid:
        best = max(valid, key=lambda s: s["savings_pct"])
        recommended = best["strategy"]
        reason = f"{best['savings_pct']:.1f}% energy savings vs baseline"

    return {
        "building_name": config.building.name,
        "building_type": config.building.building_type.value,
        "climate_city": config.climate_city,
        "baseline": baseline,
        "strategies": strategies,
        "recommended_strategy": recommended,
        "recommendation_reason": reason,
    }
