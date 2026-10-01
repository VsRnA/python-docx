from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class DocumentSourceFile:
    document_id: UUID
    filename: str
    object_key: str
    size_bytes: int
    sha256: str
    position: int
    role: str = "merge_source"
    source_document_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.filename.strip():
            raise ValueError("Source filename must not be empty")
        if not self.filename.lower().endswith(".docx"):
            raise ValueError("Source file must have .docx extension")
        if not self.object_key.strip():
            raise ValueError("Source object key must not be empty")
        if self.size_bytes <= 0:
            raise ValueError("Source file must not be empty")
        if len(self.sha256) != 64:
            raise ValueError("Source file SHA-256 must be a hex digest")
        if self.position < 1:
            raise ValueError("Source file position must be positive")
