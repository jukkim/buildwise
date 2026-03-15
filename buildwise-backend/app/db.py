"""Database session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import logging as _logging

from app.config import settings

_logger = _logging.getLogger(__name__)

# Warn if default dev credentials detected in production
if not settings.debug and "buildwise_dev" in settings.database_url:
    _logger.warning(
        "Default development database credentials detected. "
        "Set DATABASE_URL environment variable with production credentials."
    )

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a disposable session for Celery tasks.

    Uses NullPool to avoid connection sharing issues with prefork workers.
    Each call creates and disposes its own engine.
    """
    task_engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    factory = async_sessionmaker(
        task_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await task_engine.dispose()
