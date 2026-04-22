from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "enterprise_task_management",
    broker=settings.celery_broker_url,
    backend=settings.celery_broker_url,
)

celery_app.conf.update(
    task_default_queue="default",
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["app.tasks"])
