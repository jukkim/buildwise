"""Simulation orchestration service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Building
from app.models.simulation import (
    SimulationConfig,
    SimulationRun,
    SimulationStatus,
    SimulationStrategy,
)
from app.services.bps.validator import get_applicable_strategies

# City → EPW file mapping
CITY_EPW_MAP: dict[str, str] = {
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


async def create_simulation(
    db: AsyncSession,
    building: Building,
    climate_city: str,
    period_type: str,
    requested_strategies: list[str] | None,
) -> SimulationConfig:
    """Create a SimulationConfig + SimulationRun rows.

    If ``requested_strategies`` is None, auto-determine from building type / HVAC.
    """
    bps_json = building.bps_json
    hvac_type = bps_json.get("hvac", {}).get("system_type", "")

    if requested_strategies:
        strategies = requested_strategies
    else:
        strategies = get_applicable_strategies(building.building_type.value, hvac_type)

    # Always include baseline
    if "baseline" not in strategies:
        strategies.insert(0, "baseline")

    epw_file = CITY_EPW_MAP.get(climate_city, "KOR_Seoul.Ws.108.epw")

    config = SimulationConfig(
        building_id=building.id,
        climate_city=climate_city,
        epw_file=epw_file,
        period_type=period_type,
        strategies=strategies,
    )
    db.add(config)
    await db.flush()

    for strategy_str in strategies:
        run = SimulationRun(
            config_id=config.id,
            strategy=SimulationStrategy(strategy_str),
            status=SimulationStatus.PENDING,
        )
        db.add(run)

    await db.flush()
    await db.refresh(config, attribute_names=["runs"])
    return config


async def get_simulation_progress(
    db: AsyncSession,
    config_id: uuid.UUID,
) -> SimulationConfig | None:
    """Load config with all runs."""
    result = await db.execute(
        select(SimulationConfig)
        .options(selectinload(SimulationConfig.runs))
        .where(SimulationConfig.id == config_id)
    )
    return result.scalar_one_or_none()


async def cancel_simulation_runs(config: SimulationConfig) -> int:
    """Cancel pending/queued/running runs. Returns count cancelled."""
    cancelled = 0
    for run in config.runs:
        if run.status in (SimulationStatus.PENDING, SimulationStatus.QUEUED, SimulationStatus.RUNNING):
            run.status = SimulationStatus.CANCELLED
            cancelled += 1
    return cancelled
