from dataclasses import dataclass, field
from typing import Protocol

from document_service.application.ports.document_processor import ProcessedAsset


@dataclass(frozen=True, slots=True)
class MergeSource:
    source_file_id: str
    filename: str
    content: bytes
    position: int


@dataclass(frozen=True, slots=True)
class MergedDocumentResult:
    html: str
    astra_html: str
    language: str
    theme_id: str
    theme_version: str
    assets: list[ProcessedAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DocumentMerger(Protocol):
    async def merge(
        self,
        *,
        document_id: str,
        sources: list[MergeSource],
        merge_notes: str | None,
        theme_id: str,
        theme_version: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> MergedDocumentResult: ...
