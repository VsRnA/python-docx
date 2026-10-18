from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentCommentData:
    id: UUID
    document_id: UUID
    block_id: str | None
    text: str
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentSnapshotData:
    revision: int
    document_tree: dict
    pagination_snapshot: dict


class DocumentStateRepository(Protocol):
    async def get_snapshot(self, document_id: UUID, revision: int) -> DocumentSnapshotData | None: ...

    async def save_snapshot(
        self,
        document_id: UUID,
        snapshot: DocumentSnapshotData,
        *,
        snapshot_id: UUID,
        created_at: datetime,
    ) -> None: ...

    async def list_comments(self, document_id: UUID) -> list[DocumentCommentData]: ...

    async def add_comment(self, document_id: UUID, *, block_id: str | None, text: str) -> DocumentCommentData: ...

    async def update_comment(
        self,
        comment_id: UUID,
        *,
        owner_id: UUID,
        text: str | None,
        status: str | None,
    ) -> DocumentCommentData | None: ...
