from dataclasses import dataclass, field
from typing import Protocol


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


class DocumentProcessor(Protocol):
    async def process(
        self,
        *,
        document_id: str,
        filename: str,
        content: bytes,
        prompt_package_version: str,
        theme_id: str,
        theme_version: str,
    ) -> ProcessedDocument: ...
