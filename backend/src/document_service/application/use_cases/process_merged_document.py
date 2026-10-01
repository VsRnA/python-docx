from collections.abc import Awaitable, Callable
from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_merger import DocumentMerger, MergeSource
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_source_file_repository import (
    DocumentSourceFileRepository,
)
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.ports.pdf_renderer import PdfRenderer
from document_service.application.services.asset_ingestor import AssetIngestor
from document_service.application.services.asset_materializer import AssetMaterializer
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.domain.entities.document_version import DocumentVersion


class ProcessMergedDocument:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        source_files: DocumentSourceFileRepository,
        assets: AssetRepository,
        storage: ObjectStorage,
        merger: DocumentMerger,
        validator: HtmlContractValidator,
        renderer: PdfRenderer,
        *,
        prompt_package_version: str,
        theme_id: str,
        theme_version: str,
        max_asset_size_bytes: int = 25 * 1024 * 1024,
        progress_callback: Callable[[str, int], Awaitable[None]] | None = None,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._source_files = source_files
        self._assets = assets
        self._storage = storage
        self._merger = merger
        self._validator = validator
        self._renderer = renderer
        self._prompt_package_version = prompt_package_version
        self._theme_id = theme_id
        self._theme_version = theme_version
        self._progress_callback = progress_callback
        self._asset_ingestor = AssetIngestor(
            assets,
            storage,
            max_asset_size_bytes=max_asset_size_bytes,
        )
        self._asset_materializer = AssetMaterializer(assets, storage)

    async def execute(self, document_id: UUID) -> str:
        document = await self._documents.get(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} does not exist")
        sources = await self._source_files.list_by_document(document_id)
        if len(sources) < 2:
            raise ValueError("Merged document requires at least two source files")

        document.mark_processing()
        await self._documents.update(document)
        try:
            merge_sources: list[MergeSource] = []
            await self._advance("loading_sources", 10)
            for source in sources:
                content = await self._storage.get(key=source.object_key)
                merge_sources.append(
                    MergeSource(
                        source_file_id=str(source.id),
                        filename=source.filename,
                        content=content,
                        rendered_pdf=b"",
                        position=source.position,
                    )
                )
            await self._advance("astra_merging", 20)
            merged = await self._merger.merge(
                document_id=str(document.id),
                sources=merge_sources,
                merge_notes=None,
                prompt_package_version=self._prompt_package_version,
                theme_id=self._theme_id,
                theme_version=self._theme_version,
            )
            await self._advance("materializing_assets", 70)
            materialized = await self._asset_ingestor.ingest_variants(
                document_id=document.id,
                html_variants={
                    "document": merged.html,
                    "astra": merged.astra_html,
                },
                generated_assets=merged.assets,
            )
            html = materialized["document"]
            astra_html = materialized["astra"]
            await self._advance("validating_html", 80)
            self._validator.validate(html)
            self._validator.validate(astra_html)
            await self._advance("creating_revision", 85)
            await self._versions.add(
                DocumentVersion(
                    document_id=document.id,
                    revision=1,
                    html=html,
                    astra_html=astra_html,
                    theme_id=merged.theme_id,
                    theme_version=merged.theme_version,
                    created_by=None,
                    reason="initial_merge",
                )
            )
            document.mark_ready()
            await self._documents.update(document)
            await self._advance("rendering_pdf", 90)
            render_html = await self._asset_materializer.inline(html, document.id)
            pdf = await self._renderer.render(
                html=render_html,
                title=document.title,
                theme_id=merged.theme_id,
                theme_version=merged.theme_version,
            )
            key = f"documents/{document.id}/exports/revision-1.pdf"
            await self._advance("storing_pdf", 95)
            stored = await self._storage.put(key=key, content=pdf, content_type="application/pdf")
            return stored.key
        except Exception:
            document.mark_failed()
            await self._documents.update(document)
            raise

    async def _advance(self, stage: str, progress: int) -> None:
        if self._progress_callback is not None:
            await self._progress_callback(stage, progress)
