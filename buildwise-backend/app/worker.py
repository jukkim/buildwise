"""Celery application configuration."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "buildwise",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.energyplus_timeout_seconds,
    task_time_limit=settings.energyplus_timeout_seconds + 60,
    task_routes={
        "app.tasks.simulation.*": {"queue": "simulation"},
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
