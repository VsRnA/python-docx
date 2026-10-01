from typing import Protocol
from uuid import UUID

from document_service.domain.entities.document_source_file import DocumentSourceFile


class DocumentSourceFileRepository(Protocol):
    async def add_many(self, source_files: list[DocumentSourceFile]) -> None: ...

    async def list_by_document(self, document_id: UUID) -> list[DocumentSourceFile]: ...
