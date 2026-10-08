from typing import Protocol

from document_service.domain.entities.processing_profile import ProcessingProfile


class ProcessingProfileRepository(Protocol):
    async def add(self, profile: ProcessingProfile) -> None: ...
