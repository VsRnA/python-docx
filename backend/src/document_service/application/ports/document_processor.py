from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from document_service.domain.value_objects.document_metadata import PipelineMetadata, StyleSettings


@dataclass(frozen=True, slots=True)
class AstraResponseAudit:
    response_id: str | None
    model: str
    reasoning_effort: str
    output_text: str | None
    status: str
    usage: dict[str, object] = field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AstraContractError(RuntimeError):
    def __init__(self, message: str, *, raw_responses: list[str], validation_error: str, audit: AstraResponseAudit | None = None) -> None:
        super().__init__(message)
        self.raw_responses = raw_responses
        self.validation_error = validation_error
        self.audit = audit


class AstraRequestError(RuntimeError):
    def __init__(self, message: str, *, audit: AstraResponseAudit) -> None:
        super().__init__(message)
        self.audit = audit


@dataclass(frozen=True, slots=True)
class ProcessedAsset:
    external_id: str
    filename: str
    mime_type: str
    base64_data: str
    width: int | None = None
    height: int | None = None
    alt: str = ""
    source_pages: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessedDocument:
    html: str
    astra_html: str
    language: str
    theme_id: str
    theme_version: str
    assets: list[ProcessedAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pipeline_metadata: PipelineMetadata = field(default_factory=dict)
    response_audit: AstraResponseAudit | None = None


class DocumentProcessor(Protocol):
    async def process(
        self,
        *,
        document_id: str,
        filename: str,
        content: bytes,
        theme_id: str,
        theme_version: str,
        style_settings: StyleSettings | None = None,
        custom_style_reference_pdf: bytes,
    ) -> ProcessedDocument: ...
