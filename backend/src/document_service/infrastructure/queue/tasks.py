import asyncio
import logging
from uuid import UUID

from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.use_cases.process_document import ProcessDocument
from document_service.application.use_cases.process_merged_document import ProcessMergedDocument
from document_service.application.use_cases.translate_document import TranslateDocument
from document_service.domain.value_objects.profile_status import ProcessingProfileStatus
from document_service.infrastructure.ai.yandex_translator import YandexGPTTranslator
from document_service.infrastructure.composition import (
    build_document_merger,
    build_document_processor,
    build_html_validator,
    build_storage,
)
from document_service.infrastructure.config.settings import get_settings
from document_service.infrastructure.database.repositories import (
    SqlAlchemyAiResponseRepository,
    SqlAlchemyAssetRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentSourceFileRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProcessingProfileRepository,
)
from document_service.infrastructure.database.session import async_session_factory
from document_service.infrastructure.storage.timeweb_s3 import TimewebS3Storage

logger = logging.getLogger(__name__)


async def _update_job(jobs, job, stage: str, progress: int) -> None:
    job.advance(stage=stage, progress=progress)
    await jobs.update(job)


def process_document_task(document_id: str, job_id: str) -> None:
    asyncio.run(_process(UUID(document_id), UUID(job_id)))


def process_document_merge_task(document_id: str, job_id: str) -> None:
    asyncio.run(_process_merge(UUID(document_id), UUID(job_id)))


async def _process(document_id: UUID, job_id: UUID) -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        jobs = SqlAlchemyJobRepository(session)
        profiles = SqlAlchemyProcessingProfileRepository(session)
        documents = SqlAlchemyDocumentRepository(session)
        document = await documents.get(document_id)
        job = await jobs.get(job_id)
        if job is None:
            raise LookupError(f"Job {job_id} does not exist")
        if job.status != "queued":
            return
        job.start(stage="loading_source", progress=5)
        await jobs.update(job)
        logger.info("Job %s loading profile document=%s", job_id, document_id)
        profile = await profiles.get_latest(document_id)
        if profile is not None:
            profile.status = ProcessingProfileStatus.PROCESSING
            await profiles.update(profile)
            await session.commit()
        logger.info("Job %s building document processor", job_id)
        use_case = ProcessDocument(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            SqlAlchemyAssetRepository(session),
            TimewebS3Storage(settings),
            build_document_processor(settings),
            build_html_validator(),
            theme_id=settings.document_theme_id,
            theme_version=settings.document_theme_version,
            ai_responses=SqlAlchemyAiResponseRepository(session),
            progress_callback=lambda stage, progress: _update_job(jobs, job, stage, progress),
        )
        try:
            job.advance(stage="astra_processing", progress=20)
            await jobs.update(job)
            await session.commit()
            logger.info("Job %s starting document processor", job_id)
            await use_case.execute(document_id)
            if profile and profile.translation_enabled:
                document = await SqlAlchemyDocumentRepository(session).get(document_id)
                if document is None or not profile.target_language:
                    raise ValueError("Processing profile has no target language")
                document.mark_translation()
                await SqlAlchemyDocumentRepository(session).update(document)
                profile.status = ProcessingProfileStatus.TRANSLATING
                await profiles.update(profile)
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
                    HtmlContractValidator(None),
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
                profile.status = ProcessingProfileStatus.COMPLETED
                await profiles.update(profile)
                await session.commit()
            elif profile is not None:
                profile.status = ProcessingProfileStatus.COMPLETED
                await profiles.update(profile)
                await session.commit()
            job.complete()
            await jobs.update(job)
            await session.commit()
        except Exception as error:
            latest_job = await jobs.get(job_id)
            if latest_job is not None and latest_job.status == "cancelled":
                await session.rollback()
                return
            if job.status != "cancelled":
                job.fail(code=type(error).__name__, message=str(error))
                if profile is not None:
                    profile.status = ProcessingProfileStatus.FAILED
                    await profiles.update(profile)
                    if profile.translation_enabled:
                        failed_document = await SqlAlchemyDocumentRepository(session).get(document_id)
                        if failed_document is not None and failed_document.status.value in {"ready", "processing"}:
                            failed_document.mark_processing_failed()
                            await SqlAlchemyDocumentRepository(session).update(failed_document)
                await session.commit()
            await jobs.update(job)
            await session.commit()
            raise


async def _process_merge(document_id: UUID, job_id: UUID) -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        jobs = SqlAlchemyJobRepository(session)
        profiles = SqlAlchemyProcessingProfileRepository(session)
        documents = SqlAlchemyDocumentRepository(session)
        job = await jobs.get(job_id)
        if job is None:
            raise LookupError(f"Job {job_id} does not exist")
        if job.status != "queued":
            return
        job.start(stage="loading_sources", progress=5)
        await jobs.update(job)
        document = await documents.get(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} does not exist")
        profile = await profiles.get_latest(document_id)
        if profile is not None:
            profile.status = ProcessingProfileStatus.PROCESSING
            await profiles.update(profile)
            await session.commit()

        async def update_progress(stage: str, progress: int) -> None:
            job.advance(stage=stage, progress=progress)
            await jobs.update(job)

        use_case = ProcessMergedDocument(
            documents,
            SqlAlchemyDocumentVersionRepository(session),
            SqlAlchemyDocumentSourceFileRepository(session),
            SqlAlchemyAssetRepository(session),
            build_storage(settings),
            build_document_merger(settings),
            build_html_validator(),
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
                profile.status = ProcessingProfileStatus.TRANSLATING
                await profiles.update(profile)
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
                    HtmlContractValidator(None),
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
                profile.status = ProcessingProfileStatus.COMPLETED
                await profiles.update(profile)
                await session.commit()
            job.complete()
            await jobs.update(job)
            await session.commit()
        except Exception as error:
            latest_job = await jobs.get(job_id)
            if latest_job is not None and latest_job.status == "cancelled":
                await session.rollback()
                return
            if job.status != "cancelled":
                job.fail(code=type(error).__name__, message=str(error))
                if profile is not None:
                    profile.status = ProcessingProfileStatus.FAILED
                    await profiles.update(profile)
                    if profile.translation_enabled:
                        failed_document = await SqlAlchemyDocumentRepository(session).get(document_id)
                        if failed_document is not None and failed_document.status.value in {"ready", "processing"}:
                            failed_document.mark_processing_failed()
                            await SqlAlchemyDocumentRepository(session).update(failed_document)
                await session.commit()
            await jobs.update(job)
            await session.commit()
            raise
