from collections.abc import Awaitable, Callable
from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.document_processor import DocumentProcessor
from document_service.application.ports.ai_response_repository import AiResponseRepository
from document_service.application.ports.document_processor import AstraContractError, AstraRequestError
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.services.asset_ingestor import AssetIngestor
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.services.html_blocks import ensure_block_ids
from document_service.application.services.style_theme import resolve_renderer_theme
from document_service.domain.entities.document_version import DocumentVersion
from document_service.domain.value_objects.document_status import DocumentStatus


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
        theme_id: str,
        theme_version: str,
        progress_callback: Callable[[str, int], Awaitable[None]] | None = None,
        ai_responses: AiResponseRepository | None = None,
        max_asset_size_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._assets = assets
        self._storage = storage
        self._processor = processor
        self._validator = validator
        self._theme_id = theme_id
        self._theme_version = theme_version
        self._progress_callback = progress_callback
        self._ai_responses = ai_responses
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
            await self._advance("analyzing_source", 10)
            source = await self._storage.get(key=document.source_object_key)
            reference = document.style_settings.get("reference_file")
            if not isinstance(reference, dict) or not isinstance(reference.get("key"), str):
                raise ValueError("Published style reference PDF is not attached to the document")
            style_reference_pdf = await self._storage.get(key=reference["key"])
            theme_id, theme_version = resolve_renderer_theme(
                document.style_settings, self._theme_id, self._theme_version
            )
            processed = await self._processor.process(
                document_id=str(document.id),
                filename=document.source_filename,
                content=source,
                theme_id=theme_id,
                theme_version=theme_version,
                style_settings=document.style_settings,
                custom_style_reference_pdf=style_reference_pdf,
            )
            if self._ai_responses is not None and processed.response_audit is not None:
                await self._ai_responses.add(document.id, processed.response_audit)
                await self._documents.commit()
            await self._advance("analyzing_style_reference", 35)
            if processed.pipeline_metadata:
                document.pipeline_metadata = processed.pipeline_metadata
                document.source_sha256 = processed.pipeline_metadata.get("source_sha256")
                document.style_reference_sha256 = processed.pipeline_metadata.get("style_reference_sha256")
            if processed.pipeline_metadata:
                await self._documents.update(document)
            materialized = await self._asset_ingestor.ingest_variants(
                document_id=document.id,
                html_variants={
                    "document": processed.html,
                    "astra": processed.astra_html,
                },
                generated_assets=processed.assets,
            )
            html = ensure_block_ids(materialized["document"])
            astra_html = ensure_block_ids(materialized["astra"])

            self._validator.validate(html)
            self._validator.validate(astra_html)
            if await self._versions.get_current(document.id) is None:
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
                await self._documents.update(document)
                await self._documents.commit()
            current_document = await self._documents.get(document.id)
            if current_document is not None and current_document.status is not DocumentStatus.PROCESSING:
                raise RuntimeError("Document processing was cancelled")
            document.mark_ready()
            await self._documents.update(document)
        except AstraContractError as error:
            if self._ai_responses is not None and error.audit is not None:
                await self._ai_responses.add(document.id, error.audit)
            if document.status.value in {"queued", "processing"}:
                document.mark_failed()
            await self._documents.update(document)
            await self._documents.commit()
            raise RuntimeError(f"{error}: {error.validation_error}") from error
        except AstraRequestError as error:
            if self._ai_responses is not None:
                await self._ai_responses.add(document.id, error.audit)
            if document.status.value in {"queued", "processing"}:
                document.mark_failed()
                await self._documents.update(document)
            await self._documents.commit()
            raise
        except Exception:
            if document.status.value in {"queued", "processing"}:
                document.mark_failed()
                await self._documents.update(document)
            raise

    async def _advance(self, stage: str, progress: int) -> None:
        if self._progress_callback is not None:
            await self._progress_callback(stage, progress)
