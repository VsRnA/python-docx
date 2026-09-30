import base64
import re
from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.object_storage import ObjectStorage

ASSET_REFERENCE = re.compile(r"asset://([0-9a-fA-F-]{36})")


class AssetMaterializer:
    def __init__(self, assets: AssetRepository, storage: ObjectStorage) -> None:
        self._assets = assets
        self._storage = storage

    async def signed_urls(self, document_id: UUID, *, expires_seconds: int = 3600) -> dict[str, str]:
        result: dict[str, str] = {}
        for asset in await self._assets.list_by_document(document_id):
            result[str(asset.id)] = await self._storage.presign_get(
                key=asset.storage_key,
                expires_seconds=expires_seconds,
            )
        return result

    async def inline(self, html: str, document_id: UUID) -> str:
        assets = {str(item.id): item for item in await self._assets.list_by_document(document_id)}
        replacements: dict[str, str] = {}
        for asset_id in set(ASSET_REFERENCE.findall(html)):
            asset = assets.get(asset_id)
            if asset is None:
                raise ValueError(f"Unknown asset reference: {asset_id}")
            content = await self._storage.get(key=asset.storage_key)
            encoded = base64.b64encode(content).decode("ascii")
            replacements[asset_id] = f"data:{asset.mime_type};base64,{encoded}"
        return ASSET_REFERENCE.sub(lambda match: replacements[match.group(1)], html)
