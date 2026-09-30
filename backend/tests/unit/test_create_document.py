from hashlib import sha256
from uuid import UUID, uuid4

import pytest

from document_service.application.dto.document_commands import CreateDocumentCommand
from document_service.application.ports.object_storage import StoredObject
from document_service.application.use_cases.create_document import CreateDocument
from document_service.domain.entities.document import Document
from document_service.domain.value_objects.document_status import DocumentStatus


class RepositoryStub:
    def __init__(self) -> None:
        self.document: Document | None = None

    async def add(self, document: Document) -> None:
        self.document = document

    async def get(self, document_id: UUID) -> Document | None:
        return self.document if self.document and self.document.id == document_id else None


class StorageStub:
    async def put(self, *, key: str, content: bytes, content_type: str) -> StoredObject:
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256=sha256(content).hexdigest(),
            content_type=content_type,
        )


class QueueStub:
    async def enqueue_initial_processing(self, document_id: UUID, job_id: UUID) -> str:
        return str(job_id)


class JobRepositoryStub:
    def __init__(self) -> None:
        self.job = None

    async def add(self, job) -> None:
        self.job = job


@pytest.mark.asyncio
async def test_create_document_stores_and_queues_source() -> None:
    repository = RepositoryStub()
    use_case = CreateDocument(
        repository,
        StorageStub(),
        QueueStub(),
        JobRepositoryStub(),
        max_size_bytes=50 * 1024 * 1024,
    )
    content = b"PK\x03\x04fake-docx"

    result = await use_case.execute(
        CreateDocumentCommand(
            title="Factory manual",
            filename="factory.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=len(content),
            owner_id=uuid4(),
            content=content,
        )
    )

    assert repository.document is not None
    assert repository.document.id == result.document_id
    assert repository.document.status is DocumentStatus.QUEUED
    assert UUID(result.job_id)
