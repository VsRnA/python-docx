from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.job_repository import JobRepository
from document_service.domain.entities.job import Job


class GetJob:
    def __init__(self, jobs: JobRepository, documents: DocumentRepository) -> None:
        self._jobs = jobs
        self._documents = documents

    async def execute(self, job_id: UUID, *, owner_id: UUID) -> Job | None:
        job = await self._jobs.get(job_id)
        if job is None:
            return None
        document = await self._documents.get(job.document_id)
        if document is None or document.owner_id != owner_id:
            return None
        return job
