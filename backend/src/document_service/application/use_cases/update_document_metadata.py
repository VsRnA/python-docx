from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository


class RenameDocument:
    def __init__(self, documents: DocumentRepository) -> None:
        self._documents = documents

    async def execute(self, *, document_id: UUID, owner_id: UUID, title: str) -> None:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        document.rename(title)
        await self._documents.update(document)


class DeleteDocument:
    def __init__(self, documents: DocumentRepository) -> None:
        self._documents = documents

    async def execute(self, *, document_id: UUID, owner_id: UUID) -> None:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        document.delete()
        await self._documents.update(document)
