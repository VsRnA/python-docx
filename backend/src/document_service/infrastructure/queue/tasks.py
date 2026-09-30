import asyncio
from pathlib import Path
from uuid import UUID

import httpx
from openai import APIConnectionError, APITimeoutError, RateLimitError

from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.use_cases.process_document import ProcessDocument
from document_service.infrastructure.ai.astra_processor import OpenAIAstraDocumentProcessor
from document_service.infrastructure.config.settings import get_settings
from document_service.infrastructure.conversion.gotenberg_converter import (
    GotenbergDocumentPdfConverter,
)
from document_service.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyJobRepository,
)
from document_service.infrastructure.database.session import async_session_factory
from document_service.infrastructure.queue.celery_app import celery_app
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
        )
        try:
            job.advance(stage="astra_processing", progress=20)
            await jobs.update(job)
            await use_case.execute(document_id)
            job.complete()
            await jobs.update(job)
        except Exception as error:
            job.fail(code=type(error).__name__, message=str(error))
            await jobs.update(job)
            raise
