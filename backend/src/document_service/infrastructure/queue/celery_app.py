from celery import Celery

from document_service.infrastructure.config.settings import get_settings

settings = get_settings()
celery_app = Celery("document_service", broker=settings.broker_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_enable_remote_control=False,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_routes={"document_service.process_document": {"queue": "documents"}},
)
celery_app.autodiscover_tasks(["document_service.infrastructure.queue"])
