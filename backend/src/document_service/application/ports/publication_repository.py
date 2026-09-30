from typing import Protocol
from uuid import UUID

from document_service.domain.entities.publication import Publication


class PublicationRepository(Protocol):
    async def add(self, publication: Publication) -> None: ...

    async def list_by_document(self, document_id: UUID) -> list[Publication]: ...
