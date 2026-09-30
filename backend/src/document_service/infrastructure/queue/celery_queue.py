from uuid import UUID

from document_service.infrastructure.queue.celery_app import celery_app


class CeleryDocumentJobQueue:
    async def enqueue_initial_processing(self, document_id: UUID, job_id: UUID) -> str:
        result = celery_app.send_task(
            "document_service.process_document",
            kwargs={"document_id": str(document_id), "job_id": str(job_id)},
            queue="documents",
            task_id=str(job_id),
        )
        return str(result.id)
