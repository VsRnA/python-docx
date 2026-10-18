from typing import Protocol
from uuid import UUID

from document_service.application.ports.document_processor import AstraResponseAudit


class AiResponseRepository(Protocol):
    async def add(self, document_id: UUID, audit: AstraResponseAudit) -> None: ...

    async def latest_invalid_output(self, document_id: UUID) -> str | None: ...
