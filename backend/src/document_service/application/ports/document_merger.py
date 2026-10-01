from dataclasses import dataclass, field
from typing import Protocol

from document_service.application.ports.document_processor import ProcessedAsset


@dataclass(frozen=True, slots=True)
class MergeSource:
    source_file_id: str
    filename: str
    content: bytes
    rendered_pdf: bytes
    position: int
    assets: list[ProcessedAsset] = field(default_factory=list)


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
        prompt_package_version: str,
        theme_id: str,
        theme_version: str,
    ) -> MergedDocumentResult: ...
