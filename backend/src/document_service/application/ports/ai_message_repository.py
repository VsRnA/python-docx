from typing import Protocol
from uuid import UUID

from document_service.domain.entities.ai_message import AiMessage


class AiMessageRepository(Protocol):
    async def add_many(self, messages: list[AiMessage]) -> None: ...

    async def list_by_document(self, document_id: UUID, *, limit: int = 100) -> list[AiMessage]: ...
