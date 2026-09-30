from typing import Protocol
from uuid import UUID

from document_service.domain.entities.document_version import DocumentVersion


class DocumentVersionRepository(Protocol):
    async def add(self, version: DocumentVersion) -> None: ...

    async def get_current(self, document_id: UUID) -> DocumentVersion | None: ...

    async def get_revision(self, document_id: UUID, revision: int) -> DocumentVersion | None: ...

    async def list_by_document(self, document_id: UUID) -> list[DocumentVersion]: ...
