from typing import Protocol
from uuid import UUID

from document_service.domain.entities.document import Document
from document_service.domain.entities.document_version import DocumentVersion


class DocumentRepository(Protocol):
    async def add(self, document: Document) -> None: ...

    async def commit(self) -> None: ...

    async def get(self, document_id: UUID) -> Document | None: ...

    async def get_owned(self, document_id: UUID, *, owner_id: UUID) -> Document | None: ...

    async def list(
        self,
        *,
        owner_id: UUID,
        limit: int,
        offset: int,
        search: str | None = None,
        status: str | None = None,
        sort: str = "updated",
    ) -> list[Document]: ...

    async def update(self, document: Document) -> None: ...

    async def save_version_atomically(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> bool: ...
