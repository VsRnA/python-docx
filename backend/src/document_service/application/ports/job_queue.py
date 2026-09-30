from typing import Protocol
from uuid import UUID


class DocumentJobQueue(Protocol):
    async def enqueue_initial_processing(self, document_id: UUID, job_id: UUID) -> str: ...
