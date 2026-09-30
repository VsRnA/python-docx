import base64
import binascii
import re
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_processor import ProcessedAsset
from document_service.application.ports.object_storage import ObjectStorage
from document_service.domain.entities.asset import Asset


class AssetIngestor:
    def __init__(
        self,
        assets: AssetRepository,
        storage: ObjectStorage,
        *,
        max_asset_size_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self._assets = assets
        self._storage = storage
        self._max_asset_size_bytes = max_asset_size_bytes

    async def ingest(
        self,
        *,
        document_id: UUID,
        html: str,
        generated_assets: list[ProcessedAsset],
    ) -> str:
        results = await self.ingest_variants(
            document_id=document_id,
            html_variants={"document": html},
            generated_assets=generated_assets,
        )
        return results["document"]

    async def ingest_variants(
        self,
        *,
        document_id: UUID,
        html_variants: dict[str, str],
        generated_assets: list[ProcessedAsset],
    ) -> dict[str, str]:
        materialized = dict(html_variants)
        stored_assets: list[Asset] = []
        for item in generated_assets:
            try:
                content = base64.b64decode(item.base64_data, validate=True)
            except binascii.Error as error:
                raise ValueError(f"Asset {item.external_id} contains invalid base64") from error
            if len(content) > self._max_asset_size_bytes:
                raise ValueError(f"Asset {item.external_id} exceeds size limit")
            self._validate_content(content, item.mime_type, item.external_id)
            digest = sha256(content).hexdigest()
            filename = PurePosixPath(item.filename).name
            key = f"documents/{document_id}/assets/{digest}-{filename}"
            stored = await self._storage.put(key=key, content=content, content_type=item.mime_type)
            asset = Asset(
                document_id=document_id,
                storage_key=stored.key,
                mime_type=item.mime_type,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                filename=filename,
                width=item.width,
                height=item.height,
                alt=item.alt,
            )
            stored_assets.append(asset)
            for name, variant in materialized.items():
                materialized[name] = variant.replace(
                    f"asset://{item.external_id}",
                    f"asset://{asset.id}",
                )
        if stored_assets:
            await self._assets.add_many(stored_assets)
        return materialized

    @staticmethod
    def _validate_content(content: bytes, mime_type: str, external_id: str) -> None:
        signatures = {
            "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/jpeg": content.startswith(b"\xff\xd8\xff"),
            "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        }
        if mime_type in signatures and not signatures[mime_type]:
            raise ValueError(f"Asset {external_id} does not match MIME type {mime_type}")
        if mime_type != "image/svg+xml":
            if mime_type not in signatures:
                raise ValueError(f"Unsupported asset MIME type: {mime_type}")
            return
        try:
            svg = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"SVG asset {external_id} is not UTF-8") from error
        forbidden = (
            r"<\s*script\b",
            r"<\s*foreignObject\b",
            r"\son[a-z]+\s*=",
            r"(?:href|src)\s*=\s*['\"]\s*(?:https?:|//|javascript:)",
        )
        if not re.search(r"<\s*svg\b", svg, flags=re.IGNORECASE):
            raise ValueError(f"SVG asset {external_id} has no svg root")
        if any(re.search(pattern, svg, flags=re.IGNORECASE) for pattern in forbidden):
            raise ValueError(f"SVG asset {external_id} contains active or external content")
