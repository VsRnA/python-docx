from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_processor import DocumentProcessor
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.services.asset_ingestor import AssetIngestor
from document_service.domain.entities.document_version import DocumentVersion


class ProcessDocument:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        assets: AssetRepository,
        storage: ObjectStorage,
        processor: DocumentProcessor,
        validator: HtmlContractValidator,
        *,
        prompt_package_version: str,
        theme_id: str,
        theme_version: str,
        max_asset_size_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._assets = assets
        self._storage = storage
        self._processor = processor
        self._validator = validator
        self._prompt_package_version = prompt_package_version
        self._theme_id = theme_id
        self._theme_version = theme_version
        self._max_asset_size_bytes = max_asset_size_bytes
        self._asset_ingestor = AssetIngestor(
            assets,
            storage,
            max_asset_size_bytes=max_asset_size_bytes,
        )

    async def execute(self, document_id: UUID) -> None:
        document = await self._documents.get(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} does not exist")
        if not document.source_object_key:
            raise ValueError("Document has no source object")

        document.mark_processing()
        await self._documents.update(document)
        try:
            source = await self._storage.get(key=document.source_object_key)
            processed = await self._processor.process(
                document_id=str(document.id),
                filename=document.source_filename,
                content=source,
                prompt_package_version=self._prompt_package_version,
                theme_id=self._theme_id,
                theme_version=self._theme_version,
            )
            materialized = await self._asset_ingestor.ingest_variants(
                document_id=document.id,
                html_variants={
                    "document": processed.html,
                    "astra": processed.astra_html,
                },
                generated_assets=processed.assets,
            )
            html = materialized["document"]
            astra_html = materialized["astra"]

            self._validator.validate(html)
            self._validator.validate(astra_html)
            await self._versions.add(
                DocumentVersion(
                    document_id=document.id,
                    revision=1,
                    html=html,
                    astra_html=astra_html,
                    theme_id=processed.theme_id,
                    theme_version=processed.theme_version,
                    created_by=None,
                    reason="initial_import",
                )
            )
            document.mark_ready()
            await self._documents.update(document)
        except Exception:
            document.mark_failed()
            await self._documents.update(document)
            raise
