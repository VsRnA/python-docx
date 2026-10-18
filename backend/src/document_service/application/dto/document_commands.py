from dataclasses import dataclass
from uuid import UUID

from document_service.domain.value_objects.document_metadata import StyleSettings


@dataclass(frozen=True, slots=True)
class CreateDocumentCommand:
    title: str
    filename: str
    content_type: str
    size_bytes: int
    owner_id: UUID
    content: bytes
    style_version_id: UUID | None = None
    source_language: str | None = None
    target_language: str | None = None
    translation_enabled: bool = False
    style_settings: StyleSettings | None = None
    glossary_version_id: str | None = None
