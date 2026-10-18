from dataclasses import dataclass
from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.job_queue import DocumentJobQueue
from document_service.application.ports.job_repository import JobRepository
from document_service.application.ports.processing_profile_repository import ProcessingProfileRepository
from document_service.application.ports.style_repository import StyleRepository
from document_service.domain.entities.job import Job
from document_service.domain.entities.processing_profile import ProcessingProfile
from document_service.domain.value_objects.document_status import DocumentStatus


@dataclass(frozen=True, slots=True)
class StartProcessingProfileCommand:
    document_id: UUID
    owner_id: UUID
    style_version_id: UUID
    source_language: str | None = None
    target_language: str | None = None
    translation_enabled: bool = False
    glossary_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingProfileStarted:
    profile: ProcessingProfile
    job: Job


class StartProcessingProfile:
    def __init__(
        self,
        documents: DocumentRepository,
        styles: StyleRepository,
        profiles: ProcessingProfileRepository,
        jobs: JobRepository,
        queue: DocumentJobQueue,
    ) -> None:
        self._documents = documents
        self._styles = styles
        self._profiles = profiles
        self._jobs = jobs
        self._queue = queue

    async def execute(self, command: StartProcessingProfileCommand) -> ProcessingProfileStarted:
        version = await self._styles.get_version(command.style_version_id, owner_id=command.owner_id)
        if version is None or version.status != "published":
            raise ValueError("A published style version is required")
        if command.translation_enabled and not command.target_language:
            raise ValueError("Target language is required when translation is enabled")
        document = await self._documents.get(command.document_id)
        if document is None or document.owner_id != command.owner_id:
            raise LookupError("Document not found")
        if document.status not in {DocumentStatus.UPLOADED, DocumentStatus.PROCESSING_FAILED}:
            raise RuntimeError("Only an uploaded or failed document can be started again")
        profile = ProcessingProfile(
            document_id=document.id,
            style_version_id=version.id,
            source_language=command.source_language,
            target_language=command.target_language,
            translation_enabled=command.translation_enabled,
            glossary_version_id=command.glossary_version_id,
        )
        job = Job(document_id=document.id, kind="initial_processing")
        document.mark_queued()
        document.processing_job_id = job.id
        document.style_version_id = version.id
        document.style_settings = version.settings
        await self._profiles.add(profile)
        await self._jobs.add(job)
        await self._documents.update(document)
        await self._documents.commit()
        await self._queue.enqueue_initial_processing(document.id, job.id)
        return ProcessingProfileStarted(profile=profile, job=job)
