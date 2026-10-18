from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID

from document_service.application.dto.document_commands import CreateDocumentCommand
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.job_queue import DocumentJobQueue
from document_service.application.ports.job_repository import JobRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.ports.processing_profile_repository import (
    ProcessingProfileRepository,
)
from document_service.domain.entities.document import Document
from document_service.domain.entities.job import Job
from document_service.domain.entities.processing_profile import ProcessingProfile


@dataclass(frozen=True, slots=True)
class DocumentCreated:
    document_id: UUID
    job_id: str


class CreateDocument:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: ObjectStorage,
        queue: DocumentJobQueue,
        jobs: JobRepository,
        *,
        max_size_bytes: int,
        profiles: ProcessingProfileRepository | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._queue = queue
        self._jobs = jobs
        self._max_size_bytes = max_size_bytes
        self._profiles = profiles

    async def execute(self, command: CreateDocumentCommand) -> DocumentCreated:
        self._validate(command)

        document = Document(
            title=command.title,
            source_filename=command.filename,
            source_size_bytes=command.size_bytes,
            owner_id=command.owner_id,
            style_version_id=command.style_version_id,
            style_settings=command.style_settings or {},
        )
        digest = sha256(command.content).hexdigest()
        safe_name = PurePosixPath(command.filename).name
        object_key = f"documents/{document.id}/source/{digest}-{safe_name}"

        stored = await self._storage.put(
            key=object_key,
            content=command.content,
            content_type=command.content_type,
        )
        document.attach_source(stored.key)
        document.mark_queued()
        job = Job(document_id=document.id, kind="initial_processing")
        document.processing_job_id = job.id
        await self._repository.add(document)
        if command.style_version_id is not None:
            if self._profiles is None:
                raise RuntimeError("Processing profile repository is required when a style is selected")
            await self._profiles.add(
                ProcessingProfile(
                    document_id=document.id,
                    style_version_id=command.style_version_id,
                    source_language=command.source_language,
                    target_language=command.target_language,
                    translation_enabled=command.translation_enabled,
                    glossary_version_id=command.glossary_version_id,
                )
            )
        await self._jobs.add(job)
        await self._repository.commit()
        try:
            await self._queue.enqueue_initial_processing(document.id, job.id)
        except Exception:
            return DocumentCreated(document_id=document.id, job_id=str(job.id))
        return DocumentCreated(document_id=document.id, job_id=str(job.id))

    def _validate(self, command: CreateDocumentCommand) -> None:
        if command.size_bytes != len(command.content):
            raise ValueError("Declared file size does not match uploaded content")
        if command.size_bytes > self._max_size_bytes:
            limit_mb = self._max_size_bytes / (1024 * 1024)
            raise ValueError(f"DOCX file exceeds the configured {limit_mb:g} MB limit")
        if command.content_type not in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
        }:
            raise ValueError("Unsupported DOCX content type")
        if not command.content.startswith(b"PK"):
            raise ValueError("DOCX must be a ZIP-based Office document")
