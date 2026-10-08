from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class ProcessingProfile:
    document_id: UUID
    style_version_id: UUID
    source_language: str | None = None
    target_language: str | None = None
    translation_enabled: bool = False
    glossary_version_id: str | None = None
    status: str = "created"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
