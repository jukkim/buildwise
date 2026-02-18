"""API request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.bps import BPS, BPSPatch


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int


class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str | None = None


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    plan: str
    simulation_count_monthly: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    buildings_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    data: list[ProjectResponse]
    meta: PaginationMeta


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

class BuildingCreate(BaseModel):
    name: str = Field(max_length=200)
    bps: BPS


class BuildingResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    building_type: str
    bps: dict = Field(validation_alias="bps_json")
    bps_version: int
    model_3d_url: str | None
    thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class BuildingTemplateResponse(BaseModel):
    building_type: str
    name: str
    description: str
    default_bps: BPS
    baseline_eui_kwh_m2: float | None
    available_strategies: list[str]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

class SimulationStart(BaseModel):
    building_id: uuid.UUID
    climate_city: Literal[
        "Seoul", "Busan", "Daegu", "Daejeon", "Gwangju",
        "Incheon", "Gangneung", "Jeju", "Cheongju", "Ulsan",
    ] = "Seoul"
    period_type: Literal["1year", "1month_summer", "1month_winter"] = "1year"
    strategies: list[Literal[
        "baseline", "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"
    ]] | None = None


class SimulationRunResponse(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    strategy: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None

    model_config = {"from_attributes": True}


class SimulationProgressResponse(BaseModel):
    config_id: uuid.UUID
    total_strategies: int
    completed: int
    running: int
    failed: int
    runs: list[SimulationRunResponse]
    estimated_remaining_seconds: int | None = None


class SimulationHistoryItem(BaseModel):
    config_id: uuid.UUID
    climate_city: str
    period_type: str
    strategies: list[str]
    total: int
    completed: int
    failed: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class EnergyResultResponse(BaseModel):
    strategy: str
    total_energy_kwh: float
    hvac_energy_kwh: float | None
    cooling_energy_kwh: float | None
    heating_energy_kwh: float | None
    fan_energy_kwh: float | None
    eui_kwh_m2: float
    peak_demand_kw: float | None
    savings_pct: float | None
    annual_cost_krw: int | None
    annual_savings_krw: int | None


class StrategyComparisonResponse(BaseModel):
    building_name: str
    building_type: str
    climate_city: str
    baseline: EnergyResultResponse | None
    strategies: list[EnergyResultResponse]
    recommended_strategy: str | None = None
    recommendation_reason: str | None = None


class TimeSeriesPoint(BaseModel):
    time: datetime
    value: float


class TimeSeriesResponse(BaseModel):
    strategy: str
    variable: str
    resolution: str
    data: list[TimeSeriesPoint]


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

class PlanInfoResponse(BaseModel):
    plan: str
    price_monthly_usd: float
    max_buildings: int
    max_simulations_monthly: int
    allowed_strategies: list[str]
    has_pdf_export: bool


class UsageInfoResponse(BaseModel):
    plan: str
    simulations_used: int
    simulations_limit: int
    buildings_count: int
    buildings_limit: int
    credits_remaining: int
