from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.domain.entities.document_version import DocumentVersion


class ListDocumentVersions:
    def __init__(self, documents: DocumentRepository, versions: DocumentVersionRepository) -> None:
        self._documents = documents
        self._versions = versions

    async def execute(self, *, document_id: UUID, owner_id: UUID) -> list[DocumentVersion]:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        return await self._versions.list_by_document(document_id)
