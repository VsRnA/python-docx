from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class AiResponse:
    document_id: UUID
    response_id: str | None
    model: str
    reasoning_effort: str
    output_text: str | None
    status: str
    usage: dict[str, object] = field(default_factory=dict)
    error_message: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
