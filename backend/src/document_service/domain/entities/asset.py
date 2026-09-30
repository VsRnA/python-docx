from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class Asset:
    document_id: UUID
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str
    filename: str
    width: int | None = None
    height: int | None = None
    alt: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
