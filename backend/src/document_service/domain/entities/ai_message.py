from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4


@dataclass(slots=True)
class AiMessage:
    document_id: UUID
    role: Literal["user", "assistant"]
    content: str
    revision: int
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
