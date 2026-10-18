from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.services.asset_materializer import AssetMaterializer


class ExportHtmlPreview:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        storage: ObjectStorage,
        assets: AssetRepository,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._storage = storage
        self._materializer = AssetMaterializer(assets, storage)

    async def execute(self, *, document_id: UUID, owner_id: UUID) -> str:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        version = await self._versions.get_current(document_id)
        if version is None:
            raise ValueError("Document has no renderable version")
        render_html = await self._materializer.inline(version.html, document_id)
        key = f"documents/{document.id}/previews/revision-{version.revision}.html"
        stored = await self._storage.put(
            key=key,
            content=render_html.encode("utf-8"),
            content_type="text/html; charset=utf-8",
        )
        return stored.key
