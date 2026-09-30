from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateDocumentCommand:
    title: str
    filename: str
    content_type: str
    size_bytes: int
    owner_id: UUID
    content: bytes
