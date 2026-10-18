from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class AiEditProposal:
    document_id: UUID
    owner_id: UUID
    base_revision: int
    summary: str
    before_html: str
    after_html: str
    operations: list[dict]
    id: UUID = field(default_factory=uuid4)
    status: str = "pending"
    accepted_revision: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

