from uuid import UUID, uuid4

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.ports.pdf_renderer import PdfRenderer
from document_service.application.services.asset_materializer import AssetMaterializer
from document_service.application.ports.publication_repository import PublicationRepository
from document_service.domain.entities.publication import Publication


class PublishDocument:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        assets: AssetRepository,
        storage: ObjectStorage,
        renderer: PdfRenderer,
        publications: PublicationRepository,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._storage = storage
        self._renderer = renderer
        self._materializer = AssetMaterializer(assets, storage)
        self._publications = publications

    async def execute(self, *, document_id: UUID, owner_id: UUID) -> Publication:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        version = await self._versions.get_current(document_id)
        if version is None:
            raise ValueError("Document has no publishable version")
        html = await self._materializer.inline(version.html, document_id)
        bundle = await self._renderer.bundle_html(
            html=html,
            title=document.title,
            theme_id=version.theme_id,
            theme_version=version.theme_version,
        )
        publication_id = uuid4()
        key = f"documents/{document.id}/publications/{publication_id}.html"
        stored = await self._storage.put(key=key, content=bundle, content_type="text/html; charset=utf-8")
        publication = Publication(
            id=publication_id,
            document_id=document_id,
            revision=version.revision,
            object_key=stored.key,
            created_by=owner_id,
        )
        await self._publications.add(publication)
        return publication
