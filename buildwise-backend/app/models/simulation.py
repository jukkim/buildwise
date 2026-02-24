"""Simulation models: config, runs, results."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class SimulationStrategy(enum.StrEnum):
    BASELINE = "baseline"
    M0 = "m0"
    M1 = "m1"
    M2 = "m2"
    M3 = "m3"
    M4 = "m4"
    M5 = "m5"
    M6 = "m6"
    M7 = "m7"
    M8 = "m8"


class SimulationStatus(enum.StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Simulation Config (1 per simulation batch)
# ---------------------------------------------------------------------------


class SimulationConfig(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "simulation_configs"

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    climate_city: Mapped[str] = mapped_column(String(50), nullable=False)
    epw_file: Mapped[str] = mapped_column(String(100), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False, default="1year")
    period_start: Mapped[str] = mapped_column(String(10), nullable=False, default="01/01")
    period_end: Mapped[str] = mapped_column(String(10), nullable=False, default="12/31")
    timestep_per_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    strategies: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=lambda: [s.value for s in SimulationStrategy]
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    building: Mapped[Building] = relationship(back_populates="simulation_configs")
    runs: Mapped[list[SimulationRun]] = relationship(back_populates="config", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Simulation Run (1 per strategy)
# ---------------------------------------------------------------------------


class SimulationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (UniqueConstraint("config_id", "strategy", name="unique_strategy_per_config"),)

    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy: Mapped[SimulationStrategy] = mapped_column(
        Enum(SimulationStrategy, values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SimulationStatus.PENDING,
        index=True,
    )

    # File references (GCS)
    idf_url: Mapped[str | None] = mapped_column(Text)
    idf_hash: Mapped[str | None] = mapped_column(String(64))
    result_csv_url: Mapped[str | None] = mapped_column(Text)
    error_log: Mapped[str | None] = mapped_column(Text)

    # Fair comparison
    equipment_baseline_hash: Mapped[str | None] = mapped_column(String(64))
    fair_comparison_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timing
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    # Runner info
    runner_type: Mapped[str | None] = mapped_column(String(20))
    runner_id: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    config: Mapped[SimulationConfig] = relationship(back_populates="runs")
    energy_result: Mapped[EnergyResult | None] = relationship(back_populates="run", uselist=False)
    comfort_result: Mapped[ComfortResult | None] = relationship(back_populates="run", uselist=False)
    zone_results: Mapped[list[ZoneResult]] = relationship(back_populates="run", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class EnergyResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "energy_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    total_energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    hvac_energy_kwh: Mapped[float | None] = mapped_column(Float)
    cooling_energy_kwh: Mapped[float | None] = mapped_column(Float)
    heating_energy_kwh: Mapped[float | None] = mapped_column(Float)
    fan_energy_kwh: Mapped[float | None] = mapped_column(Float)
    pump_energy_kwh: Mapped[float | None] = mapped_column(Float)
    lighting_energy_kwh: Mapped[float | None] = mapped_column(Float)
    equipment_energy_kwh: Mapped[float | None] = mapped_column(Float)

    eui_kwh_m2: Mapped[float] = mapped_column(Float, nullable=False)
    peak_demand_kw: Mapped[float | None] = mapped_column(Float)
    peak_demand_month: Mapped[int | None] = mapped_column(Integer)

    savings_kwh: Mapped[float | None] = mapped_column(Float)
    savings_pct: Mapped[float | None] = mapped_column(Float)
    annual_cost_krw: Mapped[int | None] = mapped_column(Integer)
    annual_savings_krw: Mapped[int | None] = mapped_column(Integer)
    monthly_profile_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run: Mapped[SimulationRun] = relationship(back_populates="energy_result")


class ComfortResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "comfort_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    mean_pmv: Mapped[float | None] = mapped_column(Float)
    pmv_std_dev: Mapped[float | None] = mapped_column(Float)
    unmet_hours_heating: Mapped[float | None] = mapped_column(Float)
    unmet_hours_cooling: Mapped[float | None] = mapped_column(Float)
    unmet_hours_total: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run: Mapped[SimulationRun] = relationship(back_populates="comfort_result")


class ZoneResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "zone_results"
    __table_args__ = (UniqueConstraint("run_id", "zone_name", name="unique_zone_per_run"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)

    avg_temp_c: Mapped[float | None] = mapped_column(Float)
    max_temp_c: Mapped[float | None] = mapped_column(Float)
    min_temp_c: Mapped[float | None] = mapped_column(Float)
    avg_pmv: Mapped[float | None] = mapped_column(Float)
    unmet_hours: Mapped[float | None] = mapped_column(Float)
    zone_energy_kwh: Mapped[float | None] = mapped_column(Float)

    run: Mapped[SimulationRun] = relationship(back_populates="zone_results")


from app.models.project import Building  # noqa: E402, F401
