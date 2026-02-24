"""Project routes."""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.schemas.api import (
    PaginationMeta,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """GET /projects - 프로젝트 목록 (페이지네이션)."""
    base = select(Project).where(
        Project.user_id == user.id,
        Project.status != ProjectStatus.DELETED,
    )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rows = (
        (
            await db.execute(
                base.options(selectinload(Project.buildings))
                .order_by(Project.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        )
        .scalars()
        .all()
    )

    # buildings_count 주입
    projects = []
    for p in rows:
        resp = ProjectResponse.model_validate(p)
        resp.buildings_count = len(p.buildings) if p.buildings else 0
        projects.append(resp)

    return {
        "data": projects,
        "meta": PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if total else 0,
        ),
    }


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """POST /projects - 프로젝트 생성."""
    project = Project(
        user_id=user.id,
        name=body.name,
        description=body.description,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """GET /projects/{project_id} - 프로젝트 상세."""
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


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """PATCH /projects/{project_id} - 프로젝트 수정."""
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

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description

    await db.flush()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """DELETE /projects/{project_id} - 프로젝트 삭제 (소프트 삭제)."""
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

    project.status = ProjectStatus.DELETED
    await db.flush()
