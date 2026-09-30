import base64
import html as html_module
import re
from urllib.parse import unquote, urlparse
from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.domain.entities.asset import Asset

ASSET_REFERENCE = re.compile(r"asset://([0-9a-fA-F-]{36})")
EDITOR_ONLY_ATTRIBUTE = re.compile(r'\sdata-ai-(?:context|highlight)=["\'][^"\']*["\']')
IMAGE_SOURCE = re.compile(r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'])', re.IGNORECASE)


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
        html = self._restore_asset_references(html, assets)
        html = EDITOR_ONLY_ATTRIBUTE.sub("", html)
        replacements: dict[str, str] = {}
        for asset_id in set(ASSET_REFERENCE.findall(html)):
            asset = assets.get(asset_id)
            if asset is None:
                raise ValueError(f"Unknown asset reference: {asset_id}")
            content = await self._storage.get(key=asset.storage_key)
            encoded = base64.b64encode(content).decode("ascii")
            replacements[asset_id] = f"data:{asset.mime_type};base64,{encoded}"
        return ASSET_REFERENCE.sub(lambda match: replacements[match.group(1)], html)

    @staticmethod
    def _restore_asset_references(html: str, assets: dict[str, Asset]) -> str:
        storage_keys = {str(asset.storage_key): asset_id for asset_id, asset in assets.items()}

        def replace(match: re.Match[str]) -> str:
            prefix, raw_src, suffix = match.groups()
            if raw_src.startswith("asset://") or raw_src.startswith("data:"):
                return match.group(0)
            src = html_module.unescape(raw_src)
            parsed = urlparse(src)
            path = unquote(parsed.path)
            for storage_key, asset_id in storage_keys.items():
                if storage_key in path or storage_key in src:
                    return f"{prefix}asset://{asset_id}{suffix}"
            return match.group(0)

        return IMAGE_SOURCE.sub(replace, html)
