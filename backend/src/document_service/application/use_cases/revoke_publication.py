from datetime import UTC, datetime
from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.ports.publication_repository import PublicationRepository


class RevokePublication:
    def __init__(
        self,
        documents: DocumentRepository,
        publications: PublicationRepository,
        storage: ObjectStorage,
    ) -> None:
        self._documents = documents
        self._publications = publications
        self._storage = storage

    async def execute(
        self,
        *,
        document_id: UUID,
        publication_id: UUID,
        owner_id: UUID,
    ) -> bool:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            return False
        publication = await self._publications.get_for_document(publication_id, document_id)
        if publication is None:
            return False
        if publication.revoked_at is not None:
            return True
        await self._storage.delete(key=publication.object_key)
        publication.revoked_at = datetime.now(UTC)
        await self._publications.update(publication)
        return True
