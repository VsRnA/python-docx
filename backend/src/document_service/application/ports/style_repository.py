from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from document_service.domain.value_objects.document_metadata import StyleSettings


@dataclass(frozen=True, slots=True)
class StyleVersionData:
    id: UUID
    style_id: UUID
    version: int
    status: str
    manifest: dict
    manifest_sha256: str
    settings: StyleSettings
    validation_report: dict | None
    created_by: UUID
    created_at: datetime
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class StyleData:
    id: UUID
    name: str
    description: str | None
    owner_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    versions: tuple[StyleVersionData, ...] = ()


class StyleRepository(Protocol):
    async def list(self, owner_id: UUID) -> list[StyleData]: ...

    async def get(self, style_id: UUID, *, owner_id: UUID) -> StyleData | None: ...

    async def get_version(self, version_id: UUID, *, owner_id: UUID) -> StyleVersionData | None: ...

    async def get_published_version(self, version_id: UUID, *, owner_id: UUID) -> StyleVersionData | None: ...

    async def add(self, style: StyleData, version: StyleVersionData) -> None: ...

    async def ensure_default(self, style: StyleData, version: StyleVersionData) -> StyleData: ...

    async def add_version(self, version: StyleVersionData) -> None: ...

    async def update_style(self, style: StyleData) -> None: ...

    async def update_version(self, version: StyleVersionData) -> None: ...

    async def delete(self, style_id: UUID, *, owner_id: UUID) -> bool: ...

    async def archive_published_versions(self, style_id: UUID) -> None: ...

    async def commit(self) -> None: ...
