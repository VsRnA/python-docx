from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from document_service.domain.value_objects.profile_status import ProcessingProfileStatus


@dataclass(slots=True)
class ProcessingProfile:
    document_id: UUID
    style_version_id: UUID
    source_language: str | None = None
    target_language: str | None = None
    translation_enabled: bool = False
    glossary_version_id: str | None = None
    status: ProcessingProfileStatus = ProcessingProfileStatus.CREATED
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def start(self) -> None:
        if self.status not in {ProcessingProfileStatus.CREATED, ProcessingProfileStatus.FAILED}:
            raise ValueError(f"Cannot start profile from status {self.status.value}")
        self.status = ProcessingProfileStatus.PROCESSING

    def start_translation(self) -> None:
        if self.status is not ProcessingProfileStatus.PROCESSING:
            raise ValueError(f"Cannot translate profile from status {self.status.value}")
        self.status = ProcessingProfileStatus.TRANSLATING

    def complete(self) -> None:
        if self.status not in {
            ProcessingProfileStatus.PROCESSING,
            ProcessingProfileStatus.TRANSLATING,
        }:
            raise ValueError(f"Cannot complete profile from status {self.status.value}")
        self.status = ProcessingProfileStatus.COMPLETED

    def fail(self) -> None:
        if self.status not in {
            ProcessingProfileStatus.CREATED,
            ProcessingProfileStatus.PROCESSING,
            ProcessingProfileStatus.TRANSLATING,
        }:
            raise ValueError(f"Cannot fail profile from status {self.status.value}")
        self.status = ProcessingProfileStatus.FAILED
