from typing import Protocol
from uuid import UUID

from document_service.domain.entities.ai_edit_proposal import AiEditProposal


class AiEditProposalRepository(Protocol):
    async def add(self, proposal: AiEditProposal) -> None: ...

    async def get_owned(self, proposal_id: UUID, owner_id: UUID) -> AiEditProposal | None: ...

    async def mark_accepted(self, proposal_id: UUID, revision: int) -> None: ...

