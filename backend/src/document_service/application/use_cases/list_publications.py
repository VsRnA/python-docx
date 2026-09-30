from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.publication_repository import PublicationRepository
from document_service.domain.entities.publication import Publication


class ListPublications:
    def __init__(self, documents: DocumentRepository, publications: PublicationRepository) -> None:
        self._documents = documents
        self._publications = publications

    async def execute(self, *, document_id: UUID, owner_id: UUID) -> list[Publication]:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        return await self._publications.list_by_document(document_id)
