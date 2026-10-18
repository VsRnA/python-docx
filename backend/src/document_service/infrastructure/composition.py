from document_service.application.services.html_contract import HtmlContractValidator
from document_service.infrastructure.ai.astra_processor import (
    OpenAIAstraDocumentMerger,
    OpenAIAstraDocumentProcessor,
)
from document_service.infrastructure.config.settings import Settings
from document_service.infrastructure.storage.timeweb_s3 import TimewebS3Storage


def build_storage(settings: Settings) -> TimewebS3Storage:
    return TimewebS3Storage(settings)


def build_html_validator() -> HtmlContractValidator:
    return HtmlContractValidator(None)


def build_document_processor(settings: Settings) -> OpenAIAstraDocumentProcessor:
    return OpenAIAstraDocumentProcessor(settings)


def build_document_merger(settings: Settings) -> OpenAIAstraDocumentMerger:
    return OpenAIAstraDocumentMerger(settings)
