from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class DocumentVersion:
    document_id: UUID
    revision: int
    html: str
    theme_id: str
    theme_version: str
    created_by: UUID | None
    reason: str
    astra_html: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.revision <= 0:
            raise ValueError("Revision must be positive")
        if not self.html.strip():
            raise ValueError("Version HTML must not be empty")
        if not self.theme_id.strip() or not self.theme_version.strip():
            raise ValueError("Theme identifier and version are required")
