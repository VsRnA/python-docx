from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_source_file_repository import (
    DocumentSourceFileRepository,
)
from document_service.application.ports.job_queue import DocumentJobQueue
from document_service.application.ports.job_repository import JobRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.domain.entities.document import Document
from document_service.domain.entities.document_source_file import DocumentSourceFile
from document_service.domain.entities.job import Job


@dataclass(frozen=True, slots=True)
class MergeUpload:
    filename: str
    content_type: str
    size_bytes: int
    content: bytes


@dataclass(frozen=True, slots=True)
class CreateMergedDocumentCommand:
    title: str
    owner_id: UUID
    files: list[MergeUpload]
    merge_notes: str | None = None


@dataclass(frozen=True, slots=True)
class MergedDocumentCreated:
    document_id: UUID
    job_id: str
    source_count: int


class CreateMergedDocument:
    def __init__(
        self,
        documents: DocumentRepository,
        source_files: DocumentSourceFileRepository,
        storage: ObjectStorage,
        queue: DocumentJobQueue,
        jobs: JobRepository,
        *,
        max_size_bytes: int,
        max_files: int = 5,
    ) -> None:
        self._documents = documents
        self._source_files = source_files
        self._storage = storage
        self._queue = queue
        self._jobs = jobs
        self._max_size_bytes = max_size_bytes
        self._max_files = max_files

    async def execute(self, command: CreateMergedDocumentCommand) -> MergedDocumentCreated:
        self._validate(command)
        total_size = sum(file.size_bytes for file in command.files)
        document = Document(
            title=command.title,
            source_filename="merged.docx",
            source_size_bytes=total_size,
            owner_id=command.owner_id,
        )
        source_entities: list[DocumentSourceFile] = []
        for position, file in enumerate(command.files, start=1):
            digest = sha256(file.content).hexdigest()
            safe_name = PurePosixPath(file.filename).name
            object_key = f"documents/{document.id}/merge-sources/{position:03d}-{digest}-{safe_name}"
            stored = await self._storage.put(
                key=object_key,
                content=file.content,
                content_type=file.content_type,
            )
            source_entities.append(
                DocumentSourceFile(
                    document_id=document.id,
                    filename=safe_name,
                    object_key=stored.key,
                    size_bytes=file.size_bytes,
                    sha256=digest,
                    position=position,
                )
            )

        document.attach_source(source_entities[0].object_key)
        document.mark_queued()
        job = Job(document_id=document.id, kind="merge_processing")
        document.processing_job_id = job.id
        await self._documents.add(document)
        await self._source_files.add_many(source_entities)
        await self._jobs.add(job)
        await self._queue.enqueue_merge_processing(document.id, job.id)
        return MergedDocumentCreated(
            document_id=document.id,
            job_id=str(job.id),
            source_count=len(source_entities),
        )

    def _validate(self, command: CreateMergedDocumentCommand) -> None:
        if len(command.files) < 2:
            raise ValueError("At least two DOCX files are required for merge")
        if len(command.files) > self._max_files:
            raise ValueError(f"Merge supports up to {self._max_files} DOCX files")
        for file in command.files:
            if file.size_bytes != len(file.content):
                raise ValueError("Declared file size does not match uploaded content")
            if file.size_bytes > self._max_size_bytes:
                raise ValueError("DOCX file exceeds the 50 MB limit")
            if file.content_type not in {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/octet-stream",
            }:
                raise ValueError("Unsupported DOCX content type")
            if not file.filename.lower().endswith(".docx"):
                raise ValueError("Source file must have .docx extension")
            if not file.content.startswith(b"PK"):
                raise ValueError("DOCX must be a ZIP-based Office document")
