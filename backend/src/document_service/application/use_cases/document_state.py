from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_state_repository import (
    DocumentCommentData,
    DocumentSnapshotData,
    DocumentStateRepository,
)


class DocumentState:
    def __init__(self, documents: DocumentRepository, state: DocumentStateRepository) -> None:
        self._documents = documents
        self._state = state

    async def snapshot(
        self, document_id: UUID, *, owner_id: UUID
    ) -> tuple[object, DocumentSnapshotData | None, list[DocumentCommentData]] | None:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            return None
        snapshot = await self._state.get_snapshot(document_id, document.current_revision)
        comments = await self._state.list_comments(document_id)
        return document, snapshot, comments

    async def add_comment(
        self, document_id: UUID, *, owner_id: UUID, block_id: str | None, text: str
    ) -> DocumentCommentData | None:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            return None
        return await self._state.add_comment(document_id, block_id=block_id, text=text)

    async def update_comment(
        self,
        comment_id: UUID,
        *,
        owner_id: UUID,
        text: str | None,
        status: str | None,
    ) -> DocumentCommentData | None:
        return await self._state.update_comment(comment_id, owner_id=owner_id, text=text, status=status)
