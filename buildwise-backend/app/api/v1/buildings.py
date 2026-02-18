"""Building routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.project import Building, BuildingType, Project, ProjectStatus
from app.models.user import User
from app.schemas.api import BuildingCreate, BuildingResponse
from app.schemas.bps import BPS, BPSPatch
from app.services.bps.validator import validate_bps

router = APIRouter()


async def _get_project_or_404(
    project_id: uuid.UUID, user: User, db: AsyncSession
) -> Project:
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


async def _get_building_or_404(
    building_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession
) -> Building:
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
        select(Building)
        .where(Building.project_id == project_id)
        .order_by(Building.created_at.desc())
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
    for key, value in patch_data.items():
        if isinstance(value, dict) and key in current_bps:
            current_bps[key] = {**current_bps[key], **value}
        else:
            current_bps[key] = value

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
