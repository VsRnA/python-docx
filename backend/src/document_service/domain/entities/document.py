from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from document_service.domain.value_objects.document_status import DocumentStatus


@dataclass(slots=True)
class Document:
    title: str
    source_filename: str
    source_size_bytes: int
    owner_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: DocumentStatus = DocumentStatus.UPLOADED
    current_revision: int = 0
    source_object_key: str | None = None
    processing_job_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.source_filename = self.source_filename.strip()
        if not self.title:
            raise ValueError("Document title must not be empty")
        if not self.source_filename.lower().endswith(".docx"):
            raise ValueError("Source file must have .docx extension")
        if self.source_size_bytes <= 0:
            raise ValueError("Source file must not be empty")

    def mark_queued(self) -> None:
        if self.status is not DocumentStatus.UPLOADED:
            raise ValueError(f"Cannot queue document from status {self.status.value}")
        self.status = DocumentStatus.QUEUED
        self.updated_at = datetime.now(UTC)

    def attach_source(self, object_key: str) -> None:
        if not object_key.strip():
            raise ValueError("Source object key must not be empty")
        self.source_object_key = object_key
        self.updated_at = datetime.now(UTC)

    def mark_processing(self) -> None:
        if self.status not in {DocumentStatus.QUEUED, DocumentStatus.PROCESSING_FAILED}:
            raise ValueError(f"Cannot process document from status {self.status.value}")
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.now(UTC)

    def mark_ready(self) -> None:
        if self.status is not DocumentStatus.PROCESSING:
            raise ValueError(f"Cannot complete document from status {self.status.value}")
        self.status = DocumentStatus.READY
        self.current_revision = 1
        self.updated_at = datetime.now(UTC)

    def mark_failed(self) -> None:
        if self.status not in {DocumentStatus.QUEUED, DocumentStatus.PROCESSING}:
            raise ValueError(f"Cannot fail document from status {self.status.value}")
        self.status = DocumentStatus.PROCESSING_FAILED
        self.updated_at = datetime.now(UTC)

    def rename(self, title: str) -> None:
        title = title.strip()
        if not title:
            raise ValueError("Document title must not be empty")
        self.title = title
        self.updated_at = datetime.now(UTC)

    def archive(self) -> None:
        if self.status in {DocumentStatus.UPLOADED, DocumentStatus.QUEUED, DocumentStatus.PROCESSING}:
            raise ValueError("A document being processed cannot be archived")
        self.status = DocumentStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)

    def delete(self) -> None:
        if self.status in {DocumentStatus.QUEUED, DocumentStatus.PROCESSING}:
            raise ValueError("A document being processed cannot be deleted")
        self.status = DocumentStatus.DELETED
        self.updated_at = datetime.now(UTC)
