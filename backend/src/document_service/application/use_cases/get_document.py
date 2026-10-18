from dataclasses import dataclass
from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.services.asset_materializer import AssetMaterializer
from document_service.domain.value_objects.document_metadata import PipelineMetadata, StyleSettings
from document_service.domain.value_objects.document_status import DocumentStatus


@dataclass(frozen=True, slots=True)
class DocumentDetails:
    id: UUID
    title: str
    source_filename: str
    source_size_bytes: int
    status: DocumentStatus
    current_revision: int
    processing_job_id: UUID | None
    style_version_id: UUID | None
    style_settings: StyleSettings
    pipeline_metadata: PipelineMetadata
    source_sha256: str | None
    style_reference_sha256: str | None
    html: str | None
    astra_html: str | None
    theme_id: str | None
    theme_version: str | None
    asset_urls: dict[str, str]


class GetDocument:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        assets: AssetRepository,
        storage: ObjectStorage,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._storage = storage
        self._materializer = AssetMaterializer(assets, storage)

    async def execute(self, document_id: UUID, *, owner_id: UUID) -> DocumentDetails | None:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id or document.status is DocumentStatus.DELETED:
            return None
        version = await self._versions.get_current(document_id)
        initial_version = await self._versions.get_revision(document_id, 1)
        asset_urls = await self._materializer.signed_urls(document_id)
        return DocumentDetails(
            id=document.id,
            title=document.title,
            source_filename=document.source_filename,
            source_size_bytes=document.source_size_bytes,
            status=document.status,
            current_revision=document.current_revision,
            processing_job_id=document.processing_job_id,
            style_version_id=document.style_version_id,
            style_settings=document.style_settings,
            pipeline_metadata=document.pipeline_metadata,
            source_sha256=document.source_sha256,
            style_reference_sha256=document.style_reference_sha256,
            html=version.html if version else None,
            astra_html=initial_version.astra_html if initial_version else None,
            theme_id=version.theme_id if version else None,
            theme_version=version.theme_version if version else None,
            asset_urls=asset_urls,
        )
