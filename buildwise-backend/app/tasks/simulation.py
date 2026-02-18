"""Celery tasks for EnergyPlus simulation execution."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import async_session_factory
from app.models.simulation import (
    EnergyResult,
    SimulationConfig,
    SimulationRun,
    SimulationStatus,
)
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="app.tasks.simulation.run_single_strategy")
def run_single_strategy(self, run_id: str) -> dict:
    """Execute a single EnergyPlus simulation for one strategy.

    Pipeline:
    1. Load SimulationRun + config + building BPS
    2. Generate IDF file from BPS + strategy
    3. Execute EnergyPlus
    4. Parse results → EnergyResult
    5. Update run status
    """
    return _run_async(_execute_strategy(run_id, self))


async def _execute_strategy(run_id: str, task) -> dict:
    async with async_session_factory() as db:
        # 1. Load run
        result = await db.execute(
            select(SimulationRun).where(SimulationRun.id == uuid.UUID(run_id))
        )
        run = result.scalar_one_or_none()
        if run is None:
            return {"error": f"Run {run_id} not found"}

        # Mark as running
        run.status = SimulationStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            # 2. Load config + building
            config_result = await db.execute(
                select(SimulationConfig).where(SimulationConfig.id == run.config_id)
            )
            config = config_result.scalar_one()

            # 3. Generate IDF
            from app.services.idf.generator import generate_idf

            idf_content = generate_idf(
                building_id=str(config.building_id),
                config_id=str(config.id),
                strategy=run.strategy.value,
                climate_city=config.climate_city,
                epw_file=config.epw_file,
            )

            # 4. Execute EnergyPlus (placeholder - will call Docker/subprocess)
            from app.services.simulation.runner import run_energyplus

            ep_result = await run_energyplus(
                idf_content=idf_content,
                epw_file=config.epw_file,
                run_id=run_id,
            )

            # 5. Parse results
            from app.services.results.parser import parse_energyplus_output

            parsed = parse_energyplus_output(ep_result["output_dir"])

            # 6. Store results
            energy = EnergyResult(
                run_id=run.id,
                total_energy_kwh=parsed["total_energy_kwh"],
                hvac_energy_kwh=parsed.get("hvac_energy_kwh"),
                cooling_energy_kwh=parsed.get("cooling_energy_kwh"),
                heating_energy_kwh=parsed.get("heating_energy_kwh"),
                fan_energy_kwh=parsed.get("fan_energy_kwh"),
                pump_energy_kwh=parsed.get("pump_energy_kwh"),
                lighting_energy_kwh=parsed.get("lighting_energy_kwh"),
                equipment_energy_kwh=parsed.get("equipment_energy_kwh"),
                eui_kwh_m2=parsed["eui_kwh_m2"],
                peak_demand_kw=parsed.get("peak_demand_kw"),
                peak_demand_month=parsed.get("peak_demand_month"),
                savings_kwh=parsed.get("savings_kwh"),
                savings_pct=parsed.get("savings_pct"),
                annual_cost_krw=parsed.get("annual_cost_krw"),
                annual_savings_krw=parsed.get("annual_savings_krw"),
            )
            db.add(energy)

            # 7. Mark completed
            run.status = SimulationStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            if run.started_at:
                run.duration_seconds = int(
                    (run.completed_at - run.started_at).total_seconds()
                )

            await db.commit()
            logger.info("Run %s completed: EUI=%.1f kWh/m2", run_id, parsed["eui_kwh_m2"])
            return {"status": "completed", "eui": parsed["eui_kwh_m2"]}

        except Exception as exc:
            run.status = SimulationStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            run.error_log = str(exc)[:2000]
            await db.commit()
            logger.error("Run %s failed: %s", run_id, exc)
            return {"status": "failed", "error": str(exc)}


@celery_app.task(name="app.tasks.simulation.dispatch_simulation")
def dispatch_simulation(config_id: str) -> dict:
    """Dispatch all strategy runs for a simulation config."""
    return _run_async(_dispatch(config_id))


async def _dispatch(config_id: str) -> dict:
    async with async_session_factory() as db:
        result = await db.execute(
            select(SimulationRun)
            .where(SimulationRun.config_id == uuid.UUID(config_id))
            .where(SimulationRun.status == SimulationStatus.PENDING)
        )
        runs = result.scalars().all()

        dispatched = []
        for run in runs:
            run.status = SimulationStatus.QUEUED
            run.queued_at = datetime.now(timezone.utc)
            dispatched.append(str(run.id))

        await db.commit()

    # Dispatch individual strategy tasks
    for rid in dispatched:
        run_single_strategy.delay(rid)

    logger.info("Dispatched %d runs for config %s", len(dispatched), config_id)
    return {"dispatched": len(dispatched), "run_ids": dispatched}
