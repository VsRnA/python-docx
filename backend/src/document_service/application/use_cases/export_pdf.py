from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.ports.pdf_renderer import PdfRenderer
from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.services.asset_materializer import AssetMaterializer


class ExportPdf:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        storage: ObjectStorage,
        renderer: PdfRenderer,
        assets: AssetRepository,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._storage = storage
        self._renderer = renderer
        self._materializer = AssetMaterializer(assets, storage)

    async def execute(self, *, document_id: UUID, owner_id: UUID) -> str:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        version = await self._versions.get_current(document_id)
        if version is None:
            raise ValueError("Document has no renderable version")
        render_html = await self._materializer.inline(version.html, document_id)
        pdf = await self._renderer.render(
            html=render_html,
            title=document.title,
            theme_id=version.theme_id,
            theme_version=version.theme_version,
        )
        key = f"documents/{document.id}/exports/revision-{version.revision}.pdf"
        stored = await self._storage.put(key=key, content=pdf, content_type="application/pdf")
        return stored.key
