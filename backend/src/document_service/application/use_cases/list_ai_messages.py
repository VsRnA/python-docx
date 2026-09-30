from uuid import UUID

from document_service.application.ports.ai_message_repository import AiMessageRepository
from document_service.application.ports.document_repository import DocumentRepository
from document_service.domain.entities.ai_message import AiMessage


class ListAiMessages:
    def __init__(self, documents: DocumentRepository, messages: AiMessageRepository) -> None:
        self._documents = documents
        self._messages = messages

    async def execute(self, *, document_id: UUID, owner_id: UUID, limit: int = 100) -> list[AiMessage]:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        return await self._messages.list_by_document(document_id, limit=limit)
