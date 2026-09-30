from document_service.application.ports.document_repository import DocumentRepository
from document_service.domain.entities.document import Document
from uuid import UUID


class ListDocuments:
    def __init__(self, documents: DocumentRepository) -> None:
        self._documents = documents

    async def execute(self, *, owner_id: UUID, limit: int = 50, offset: int = 0) -> list[Document]:
        return await self._documents.list(owner_id=owner_id, limit=limit, offset=offset)
