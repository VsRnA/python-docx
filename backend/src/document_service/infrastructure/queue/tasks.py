import asyncio
from pathlib import Path
from uuid import UUID

import httpx
from openai import APIConnectionError, APITimeoutError, RateLimitError
from sqlalchemy import select

from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.use_cases.process_document import ProcessDocument
from document_service.application.use_cases.process_merged_document import ProcessMergedDocument
from document_service.application.use_cases.translate_document import TranslateDocument
from document_service.infrastructure.ai.astra_processor import (
    OpenAIAstraDocumentMerger,
    OpenAIAstraDocumentProcessor,
)
from document_service.infrastructure.config.settings import get_settings
from document_service.infrastructure.conversion.gotenberg_converter import (
    GotenbergDocumentPdfConverter,
)
from document_service.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentSourceFileRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyJobRepository,
)
from document_service.infrastructure.database.session import async_session_factory
from document_service.infrastructure.database.models import (
    DocumentModel,
    DocumentStyleVersionModel,
    ProcessingProfileModel,
)
from document_service.infrastructure.queue.celery_app import celery_app
from document_service.infrastructure.renderer.http_pdf_renderer import HttpPdfRenderer
from document_service.infrastructure.storage.timeweb_s3 import TimewebS3Storage


@celery_app.task(
    bind=True,
    name="document_service.process_document",
    autoretry_for=(
        ConnectionError,
        TimeoutError,
        httpx.TransportError,
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
    ),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=4,
)
def process_document_task(self, document_id: str, job_id: str) -> None:
    asyncio.run(_process(UUID(document_id), UUID(job_id)))


@celery_app.task(
    bind=True,
    name="document_service.process_document_merge",
    autoretry_for=(
        ConnectionError,
        TimeoutError,
        httpx.TransportError,
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
    ),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=4,
)
def process_document_merge_task(self, document_id: str, job_id: str) -> None:
    asyncio.run(_process_merge(UUID(document_id), UUID(job_id)))


async def _process(document_id: UUID, job_id: UUID) -> None:
    settings = get_settings()
    prompt_root = Path(settings.prompt_root)
    allowed_classes = set(
        (prompt_root / settings.prompt_package_version / "classes.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    async with async_session_factory() as session:
        jobs = SqlAlchemyJobRepository(session)
        job = await jobs.get(job_id)
        if job is None:
            raise LookupError(f"Job {job_id} does not exist")
        job.start(stage="loading_source", progress=5)
        await jobs.update(job)
        profile = await session.scalar(
            select(ProcessingProfileModel)
            .where(ProcessingProfileModel.document_id == document_id)
            .order_by(ProcessingProfileModel.created_at.desc())
        )
        if profile is not None:
            profile.status = "processing"
            await session.commit()
        custom_reference = None
        if profile is not None:
            style_version = await session.get(DocumentStyleVersionModel, profile.style_version_id)
            reference = (style_version.settings or {}).get("reference_file") if style_version else None
            if isinstance(reference, dict) and isinstance(reference.get("key"), str):
                custom_reference = await TimewebS3Storage(settings).get(key=reference["key"])
        use_case = ProcessDocument(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            SqlAlchemyAssetRepository(session),
            TimewebS3Storage(settings),
            OpenAIAstraDocumentProcessor(
                settings,
                prompt_root,
                source_pdf_converter=GotenbergDocumentPdfConverter(
                    settings.docx_converter_url,
                    timeout_seconds=settings.docx_converter_timeout_seconds,
                ),
            ),
            HtmlContractValidator(allowed_classes),
            prompt_package_version=settings.prompt_package_version,
            theme_id=settings.document_theme_id,
            theme_version=settings.document_theme_version,
            custom_style_reference_pdf=custom_reference,
        )
        try:
            job.advance(stage="astra_processing", progress=20)
            await jobs.update(job)
            await use_case.execute(document_id)
            if profile and profile.translation_enabled:
                document = await SqlAlchemyDocumentRepository(session).get(document_id)
                if document is None or not profile.target_language:
                    raise ValueError("Processing profile has no target language")
                document.mark_translation()
                await SqlAlchemyDocumentRepository(session).update(document)
                profile.status = "translating"
                job.advance(stage="translation", progress=82)
                await session.commit()
                await jobs.update(job)
                await TranslateDocument(
                    SqlAlchemyDocumentRepository(session),
                    SqlAlchemyDocumentVersionRepository(session),
                    YandexGPTTranslator(
                        api_key=settings.yandex_gpt_api_key,
                        folder_id=settings.yandex_folder_id,
                        model_uri=settings.yandex_model_uri,
                    ),
                    HtmlContractValidator(allowed_classes),
                ).execute(
                    document_id=document_id,
                    owner_id=document.owner_id,
                    base_revision=document.current_revision,
                    source_language=profile.source_language or "auto",
                    target_language=profile.target_language,
                    glossary_version=profile.glossary_version_id,
                )
                document = await SqlAlchemyDocumentRepository(session).get(document_id)
                if document is None:
                    raise LookupError("Document disappeared after translation")
                document.mark_ready()
                await SqlAlchemyDocumentRepository(session).update(document)
                profile.status = "completed"
                await session.commit()
            elif profile is not None:
                profile.status = "completed"
                await session.commit()
            job.complete()
            await jobs.update(job)
        except Exception as error:
            if job.status != "cancelled":
                job.fail(code=type(error).__name__, message=str(error))
                if profile is not None:
                    profile.status = "failed"
                    if profile.translation_enabled:
                        document_model = await session.get(DocumentModel, document_id)
                        if document_model is not None and document_model.status in {"ready", "processing"}:
                            document_model.status = "processing_failed"
                await session.commit()
            await jobs.update(job)
            raise


async def _process_merge(document_id: UUID, job_id: UUID) -> None:
    settings = get_settings()
    prompt_root = Path(settings.prompt_root)
    allowed_classes = set(
        (prompt_root / settings.prompt_package_version / "classes.txt")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    async with async_session_factory() as session:
        jobs = SqlAlchemyJobRepository(session)
        job = await jobs.get(job_id)
        if job is None:
            raise LookupError(f"Job {job_id} does not exist")
        job.start(stage="loading_sources", progress=5)
        await jobs.update(job)
        profile = await session.scalar(
            select(ProcessingProfileModel)
            .where(ProcessingProfileModel.document_id == document_id)
            .order_by(ProcessingProfileModel.created_at.desc())
        )
        if profile is not None:
            profile.status = "processing"
            await session.commit()

        async def update_progress(stage: str, progress: int) -> None:
            job.advance(stage=stage, progress=progress)
            await jobs.update(job)

        use_case = ProcessMergedDocument(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            SqlAlchemyDocumentSourceFileRepository(session),
            SqlAlchemyAssetRepository(session),
            TimewebS3Storage(settings),
            OpenAIAstraDocumentMerger(
                settings,
                prompt_root.parent / "docx-merge",
                source_pdf_converter=GotenbergDocumentPdfConverter(
                    settings.docx_converter_url,
                    timeout_seconds=settings.docx_converter_timeout_seconds,
                ),
            ),
            HtmlContractValidator(allowed_classes),
            HttpPdfRenderer(settings.renderer_url),
            prompt_package_version="v1",
            theme_id=settings.document_theme_id,
            theme_version=settings.document_theme_version,
            progress_callback=update_progress,
        )
        try:
            await use_case.execute(document_id)
            if profile and profile.translation_enabled:
                document = await SqlAlchemyDocumentRepository(session).get(document_id)
                if document is None or not profile.target_language:
                    raise ValueError("Processing profile has no target language")
                document.mark_translation()
                await SqlAlchemyDocumentRepository(session).update(document)
                profile.status = "translating"
                job.advance(stage="translation", progress=82)
                await session.commit()
                await jobs.update(job)
                await TranslateDocument(
                    SqlAlchemyDocumentRepository(session),
                    SqlAlchemyDocumentVersionRepository(session),
                    YandexGPTTranslator(
                        api_key=settings.yandex_gpt_api_key,
                        folder_id=settings.yandex_folder_id,
                        model_uri=settings.yandex_model_uri,
                    ),
                    HtmlContractValidator(allowed_classes),
                ).execute(
                    document_id=document_id,
                    owner_id=document.owner_id,
                    base_revision=document.current_revision,
                    source_language=profile.source_language or "auto",
                    target_language=profile.target_language,
                    glossary_version=profile.glossary_version_id,
                )
                document = await SqlAlchemyDocumentRepository(session).get(document_id)
                if document is None:
                    raise LookupError("Document disappeared after translation")
                document.mark_ready()
                await SqlAlchemyDocumentRepository(session).update(document)
            if profile is not None:
                profile.status = "completed"
                await session.commit()
            job.complete()
            await jobs.update(job)
        except Exception as error:
            if job.status != "cancelled":
                job.fail(code=type(error).__name__, message=str(error))
                if profile is not None:
                    profile.status = "failed"
                    if profile.translation_enabled:
                        document_model = await session.get(DocumentModel, document_id)
                        if document_model is not None and document_model.status in {"ready", "processing"}:
                            document_model.status = "processing_failed"
                await session.commit()
            await jobs.update(job)
            raise
