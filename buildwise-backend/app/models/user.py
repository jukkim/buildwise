"""User and subscription models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserPlan(enum.StrEnum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    auth0_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    plan: Mapped[UserPlan] = mapped_column(
        Enum(UserPlan, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=UserPlan.FREE
    )
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    simulation_count_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    simulation_count_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    projects: Mapped[list[Project]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscription: Mapped[Subscription | None] = relationship(back_populates="user", uselist=False)


class Subscription(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plan: Mapped[UserPlan] = mapped_column(
        Enum(UserPlan, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=UserPlan.FREE
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="subscription")


# Avoid circular import - Project is imported at runtime
from app.models.project import Project  # noqa: E402, F401
