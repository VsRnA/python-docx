from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.job_queue import DocumentJobQueue
from document_service.application.ports.job_repository import JobRepository
from document_service.domain.entities.job import Job


class CancelJob:
    def __init__(
        self,
        jobs: JobRepository,
        documents: DocumentRepository,
        queue: DocumentJobQueue,
    ) -> None:
        self._jobs = jobs
        self._documents = documents
        self._queue = queue

    async def execute(self, job_id: UUID, *, owner_id: UUID) -> Job | None:
        job = await self._jobs.get(job_id)
        if job is None:
            return None
        document = await self._documents.get(job.document_id)
        if document is None or document.owner_id != owner_id:
            return None
        was_queued = job.status.value == "queued"
        await self._queue.revoke(job_id, terminate=not was_queued)
        job.cancel()
        await self._jobs.update(job)
        if document.status.value in {"queued", "processing"}:
            document.mark_failed()
            document.processing_job_id = job.id
            await self._documents.update(document)
        return job
