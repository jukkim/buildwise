"""Celery tasks for EnergyPlus simulation execution."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import async_session_factory
from app.models.project import Building
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
    4. Parse results -> EnergyResult
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

        # Check if already cancelled before starting
        if run.status == SimulationStatus.CANCELLED:
            logger.info("Run %s already cancelled, skipping", run_id)
            return {"status": "cancelled"}

        # Mark as running
        run.status = SimulationStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            # 2. Load config + building
            config_result = await db.execute(
                select(SimulationConfig)
                .options(selectinload(SimulationConfig.building))
                .where(SimulationConfig.id == run.config_id)
            )
            config = config_result.scalar_one()
            building = config.building

            # 3. Demo mode or real E+ execution
            use_mock = settings.debug or not bool(settings.energyplus_image)

            if use_mock:
                # Mock mode: return pre-computed realistic results
                import asyncio as _aio
                from app.services.simulation.mock_runner import generate_mock_result

                await _aio.sleep(2)  # Simulate processing time
                area = building.bps_json.get("geometry", {}).get("total_floor_area_m2", 1000)
                parsed = generate_mock_result(
                    building_type=building.building_type.value,
                    climate_city=config.climate_city,
                    strategy=run.strategy.value,
                    total_floor_area_m2=area,
                )
            else:
                # Real E+ execution
                from app.services.idf.generator import generate_idf
                from app.services.results.parser import parse_energyplus_output
                from app.services.simulation.runner import run_energyplus

                idf_content = generate_idf(
                    building_id=str(config.building_id),
                    config_id=str(config.id),
                    strategy=run.strategy.value,
                    climate_city=config.climate_city,
                    epw_file=config.epw_file,
                    bps=building.bps_json,
                )
                ep_result = await run_energyplus(
                    idf_content=idf_content,
                    epw_file=config.epw_file,
                    run_id=run_id,
                )
                try:
                    parsed = parse_energyplus_output(ep_result["output_dir"])
                finally:
                    # Clean up temp files after parsing
                    from app.services.simulation.runner import cleanup_run_directory
                    cleanup_run_directory(run_id)

            # Re-check cancellation before storing results
            await db.refresh(run, ["status"])
            if run.status == SimulationStatus.CANCELLED:
                logger.info("Run %s cancelled during execution, discarding results", run_id)
                return {"status": "cancelled"}

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
        run_objects = []
        for run in runs:
            run.status = SimulationStatus.QUEUED
            run.queued_at = datetime.now(timezone.utc)
            dispatched.append(str(run.id))
            run_objects.append(run)

        await db.commit()

    # Dispatch individual strategy tasks and store task IDs
    async with async_session_factory() as db:
        for i, rid in enumerate(dispatched):
            async_result = run_single_strategy.delay(rid)
            # Store Celery task ID in runner_id for later revocation
            run_obj = await db.execute(
                select(SimulationRun).where(SimulationRun.id == uuid.UUID(rid))
            )
            run = run_obj.scalar_one()
            run.runner_id = async_result.id
            run.runner_type = "celery"
        await db.commit()

    logger.info("Dispatched %d runs for config %s", len(dispatched), config_id)
    return {"dispatched": len(dispatched), "run_ids": dispatched}
