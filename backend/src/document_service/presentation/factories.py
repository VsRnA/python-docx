from sqlalchemy.ext.asyncio import AsyncSession

from document_service.infrastructure.ai.astra_processor import OpenAIAstraDocumentProcessor as _OpenAIAstraDocumentProcessor
from document_service.infrastructure.ai.yandex_translator import YandexGPTTranslator as _YandexGPTTranslator
from document_service.infrastructure.config.settings import Settings
from document_service.infrastructure.database.repositories import (
    SqlAlchemyAiMessageRepository as _SqlAlchemyAiMessageRepository,
    SqlAlchemyAiResponseRepository as _SqlAlchemyAiResponseRepository,
    SqlAlchemyAssetRepository as _SqlAlchemyAssetRepository,
    SqlAlchemyDocumentRepository as _SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentSourceFileRepository as _SqlAlchemyDocumentSourceFileRepository,
    SqlAlchemyDocumentStateRepository as _SqlAlchemyDocumentStateRepository,
    SqlAlchemyDocumentVersionRepository as _SqlAlchemyDocumentVersionRepository,
    SqlAlchemyJobRepository as _SqlAlchemyJobRepository,
    SqlAlchemyProcessingProfileRepository as _SqlAlchemyProcessingProfileRepository,
    SqlAlchemyPublicationRepository as _SqlAlchemyPublicationRepository,
    SqlAlchemyStyleRepository as _SqlAlchemyStyleRepository,
)
from document_service.infrastructure.queue.postgres_queue import PostgresDocumentJobQueue as _PostgresDocumentJobQueue
from document_service.infrastructure.storage.timeweb_s3 import TimewebS3Storage as _TimewebS3Storage


def document_repository(session: AsyncSession) -> _SqlAlchemyDocumentRepository:
    return _SqlAlchemyDocumentRepository(session)


def document_version_repository(session: AsyncSession) -> _SqlAlchemyDocumentVersionRepository:
    return _SqlAlchemyDocumentVersionRepository(session)


def asset_repository(session: AsyncSession) -> _SqlAlchemyAssetRepository:
    return _SqlAlchemyAssetRepository(session)


def document_state_repository(session: AsyncSession) -> _SqlAlchemyDocumentStateRepository:
    return _SqlAlchemyDocumentStateRepository(session)


def job_repository(session: AsyncSession) -> _SqlAlchemyJobRepository:
    return _SqlAlchemyJobRepository(session)


def processing_profile_repository(session: AsyncSession) -> _SqlAlchemyProcessingProfileRepository:
    return _SqlAlchemyProcessingProfileRepository(session)


def style_repository(session: AsyncSession) -> _SqlAlchemyStyleRepository:
    return _SqlAlchemyStyleRepository(session)


def publication_repository(session: AsyncSession) -> _SqlAlchemyPublicationRepository:
    return _SqlAlchemyPublicationRepository(session)


def ai_message_repository(session: AsyncSession) -> _SqlAlchemyAiMessageRepository:
    return _SqlAlchemyAiMessageRepository(session)


def ai_response_repository(session: AsyncSession) -> _SqlAlchemyAiResponseRepository:
    return _SqlAlchemyAiResponseRepository(session)


def source_file_repository(session: AsyncSession) -> _SqlAlchemyDocumentSourceFileRepository:
    return _SqlAlchemyDocumentSourceFileRepository(session)


def object_storage(settings: Settings) -> _TimewebS3Storage:
    return _TimewebS3Storage(settings)


def document_queue() -> _PostgresDocumentJobQueue:
    return _PostgresDocumentJobQueue()


def astra_processor(settings: Settings) -> _OpenAIAstraDocumentProcessor:
    return _OpenAIAstraDocumentProcessor(settings)


def yandex_translator(settings: Settings) -> _YandexGPTTranslator:
    return _YandexGPTTranslator(
        api_key=settings.yandex_gpt_api_key,
        folder_id=settings.yandex_folder_id,
        model_uri=settings.yandex_model_uri,
    )


SqlAlchemyAiMessageRepository = ai_message_repository
SqlAlchemyAssetRepository = asset_repository
SqlAlchemyDocumentRepository = document_repository
SqlAlchemyDocumentSourceFileRepository = source_file_repository
SqlAlchemyDocumentStateRepository = document_state_repository
SqlAlchemyDocumentVersionRepository = document_version_repository
SqlAlchemyJobRepository = job_repository
SqlAlchemyProcessingProfileRepository = processing_profile_repository
SqlAlchemyPublicationRepository = publication_repository
SqlAlchemyStyleRepository = style_repository
PostgresDocumentJobQueue = document_queue
TimewebS3Storage = object_storage
OpenAIAstraDocumentProcessor = astra_processor
YandexGPTTranslator = yandex_translator
