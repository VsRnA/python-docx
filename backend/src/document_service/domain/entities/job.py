from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class Job:
    document_id: UUID
    kind: str
    id: UUID = field(default_factory=uuid4)
    status: str = "queued"
    progress: int = 0
    stage: str = "queued"
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self, *, stage: str = "processing", progress: int = 5) -> None:
        self.status = "running"
        self.stage = stage
        self.progress = progress
        self.started_at = datetime.now(UTC)
        self.finished_at = None
        self.error_code = None
        self.error_message = None

    def advance(self, *, stage: str, progress: int) -> None:
        if not 0 <= progress <= 100:
            raise ValueError("Job progress must be between 0 and 100")
        self.stage = stage
        self.progress = progress

    def complete(self) -> None:
        self.status = "completed"
        self.stage = "completed"
        self.progress = 100
        self.finished_at = datetime.now(UTC)

    def fail(self, *, code: str, message: str) -> None:
        self.status = "failed"
        self.stage = "failed"
        self.error_code = code
        self.error_message = message[:4000]
        self.finished_at = datetime.now(UTC)
