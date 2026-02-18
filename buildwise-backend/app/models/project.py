"""Project and building models."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class BuildingType(str, enum.Enum):
    LARGE_OFFICE = "large_office"
    MEDIUM_OFFICE = "medium_office"
    SMALL_OFFICE = "small_office"
    STANDALONE_RETAIL = "standalone_retail"
    PRIMARY_SCHOOL = "primary_school"
    HOSPITAL = "hospital"


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), nullable=False, default=ProjectStatus.ACTIVE
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="projects")
    buildings: Mapped[list["Building"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Building(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "buildings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    building_type: Mapped[BuildingType] = mapped_column(Enum(BuildingType), nullable=False)
    bps_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    bps_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model_3d_url: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="buildings")
    simulation_configs: Mapped[list["SimulationConfig"]] = relationship(
        back_populates="building", cascade="all, delete-orphan"
    )


from app.models.simulation import SimulationConfig  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
