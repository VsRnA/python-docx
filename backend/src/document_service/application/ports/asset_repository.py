from typing import Protocol
from uuid import UUID

from document_service.domain.entities.asset import Asset


class AssetRepository(Protocol):
    async def add_many(self, assets: list[Asset]) -> None: ...

    async def list_by_document(self, document_id: UUID) -> list[Asset]: ...

    async def get(self, asset_id: UUID) -> Asset | None: ...
