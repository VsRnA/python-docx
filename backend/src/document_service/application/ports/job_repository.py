from typing import Protocol
from uuid import UUID

from document_service.domain.entities.job import Job


class JobRepository(Protocol):
    async def add(self, job: Job) -> None: ...

    async def get(self, job_id: UUID) -> Job | None: ...

    async def update(self, job: Job) -> None: ...

    async def renew_lease(self, job_id: UUID, owner: str, lease_seconds: int = 900) -> bool: ...
