"""Building routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models.project import Building, BuildingType, Project, ProjectStatus
from app.models.simulation import SimulationConfig, SimulationStatus
from app.models.user import User
from app.schemas.api import BuildingCreate, BuildingResponse, BuildingUpdate, SimulationHistoryItem
from app.schemas.bps import BPS, BPSPatch
from app.api.v1.billing import _PLANS
from app.services.bps.validator import validate_bps

router = APIRouter()


async def _get_project_or_404(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user.id,
            Project.status != ProjectStatus.DELETED,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _get_building_or_404(building_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession) -> Building:
    result = await db.execute(
        select(Building).where(
            Building.id == building_id,
            Building.project_id == project_id,
        )
    )
    building = result.scalar_one_or_none()
    if building is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    return building


@router.get("/{project_id}/buildings", response_model=list[BuildingResponse])
async def list_buildings(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Building]:
    """GET /projects/{project_id}/buildings - 건물 목록."""
    await _get_project_or_404(project_id, user, db)
    result = await db.execute(
        select(Building).where(Building.project_id == project_id).order_by(Building.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{project_id}/buildings",
    response_model=BuildingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_building(
    project_id: uuid.UUID,
    body: BuildingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Building:
    """POST /projects/{project_id}/buildings - 건물 생성."""
    await _get_project_or_404(project_id, user, db)

    # Check building count limit
    plan_info = _PLANS.get(user.plan.value, _PLANS["free"])
    max_buildings = plan_info["max_buildings"]
    result = await db.execute(
        select(func.count(Building.id))
        .join(Building.project)
        .where(Project.user_id == user.id)
        .where(Project.status != ProjectStatus.DELETED)
    )
    buildings_count = result.scalar() or 0
    if buildings_count >= max_buildings:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Building limit reached ({max_buildings}). Upgrade your plan for more.",
        )

    # BPS domain validation
    errors = validate_bps(body.bps)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "bps_validation_error", "errors": errors},
        )

    building = Building(
        project_id=project_id,
        name=body.name,
        building_type=BuildingType(body.bps.geometry.building_type),
        bps_json=body.bps.model_dump(mode="json"),
        bps_version=1,
    )
    db.add(building)
    await db.flush()
    await db.refresh(building)
    return building


@router.get("/{project_id}/buildings/{building_id}", response_model=BuildingResponse)
async def get_building(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Building:
    """GET /projects/{project_id}/buildings/{building_id} - 건물 상세."""
    await _get_project_or_404(project_id, user, db)
    building = await _get_building_or_404(building_id, project_id, db)
    return building


@router.patch(
    "/{project_id}/buildings/{building_id}",
    response_model=BuildingResponse,
)
async def update_building(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    body: BuildingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Building:
    """PATCH /projects/{project_id}/buildings/{building_id} - 건물 정보 수정."""
    await _get_project_or_404(project_id, user, db)
    building = await _get_building_or_404(building_id, project_id, db)

    if body.name is not None:
        building.name = body.name

    await db.flush()
    await db.refresh(building)
    return building


@router.patch(
    "/{project_id}/buildings/{building_id}/bps",
    response_model=BuildingResponse,
)
async def update_bps(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    patch: BPSPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Building:
    """PATCH /projects/{project_id}/buildings/{building_id}/bps - BPS 부분 수정."""
    await _get_project_or_404(project_id, user, db)
    building = await _get_building_or_404(building_id, project_id, db)

    current_bps = dict(building.bps_json)
    patch_data = patch.model_dump(exclude_none=True)

    def _deep_merge(base: dict, patch: dict) -> dict:
        """Recursively merge patch into base dict."""
        merged = dict(base)
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = _deep_merge(merged[k], v)
            else:
                merged[k] = v
        return merged

    current_bps = _deep_merge(current_bps, patch_data)

    # Validate merged BPS
    try:
        merged_bps = BPS.model_validate(current_bps)
        errors = validate_bps(merged_bps)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "bps_validation_error", "errors": errors},
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "bps_validation_error", "errors": [str(exc)]},
        )

    building.bps_json = current_bps
    building.bps_version += 1

    if "geometry" in patch_data and "building_type" in patch_data["geometry"]:
        building.building_type = BuildingType(patch_data["geometry"]["building_type"])

    await db.flush()
    await db.refresh(building)
    return building


@router.post(
    "/{project_id}/buildings/{building_id}/clone",
    response_model=BuildingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_building(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Building:
    """POST /projects/{project_id}/buildings/{building_id}/clone - 건물 복제."""
    await _get_project_or_404(project_id, user, db)
    source = await _get_building_or_404(building_id, project_id, db)

    clone = Building(
        project_id=project_id,
        name=f"{source.name} (Copy)",
        building_type=source.building_type,
        bps_json=dict(source.bps_json),
        bps_version=1,
    )
    db.add(clone)
    await db.flush()
    await db.refresh(clone)
    return clone


@router.delete(
    "/{project_id}/buildings/{building_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_building(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """DELETE /projects/{project_id}/buildings/{building_id} - 건물 삭제."""
    await _get_project_or_404(project_id, user, db)
    building = await _get_building_or_404(building_id, project_id, db)
    await db.delete(building)
    await db.flush()


@router.get(
    "/{project_id}/buildings/{building_id}/simulations",
    response_model=list[SimulationHistoryItem],
)
async def list_building_simulations(
    project_id: uuid.UUID,
    building_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """GET /projects/{project_id}/buildings/{building_id}/simulations - 시뮬레이션 히스토리."""
    await _get_project_or_404(project_id, user, db)
    await _get_building_or_404(building_id, project_id, db)

    result = await db.execute(
        select(SimulationConfig)
        .options(selectinload(SimulationConfig.runs))
        .where(SimulationConfig.building_id == building_id)
        .order_by(SimulationConfig.created_at.desc())
    )
    configs = result.scalars().all()

    items = []
    for cfg in configs:
        completed = sum(1 for r in cfg.runs if r.status == SimulationStatus.COMPLETED)
        failed = sum(1 for r in cfg.runs if r.status == SimulationStatus.FAILED)
        items.append(
            {
                "config_id": cfg.id,
                "climate_city": cfg.climate_city,
                "period_type": cfg.period_type,
                "strategies": cfg.strategies,
                "total": len(cfg.runs),
                "completed": completed,
                "failed": failed,
                "created_at": cfg.created_at,
            }
        )

    return items
