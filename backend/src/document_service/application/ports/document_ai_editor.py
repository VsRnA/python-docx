from dataclasses import dataclass, field
from typing import Literal, Protocol

from document_service.application.ports.document_processor import ProcessedAsset


@dataclass(frozen=True, slots=True)
class ChangeOperation:
    operation: Literal["replace_block", "delete_block", "insert_after"]
    block_id: str
    expected_hash: str
    html: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentChangeSet:
    base_revision: int
    summary: str
    operations: list[ChangeOperation]
    assets: list[ProcessedAsset] = field(default_factory=list)

class DocumentAiEditor(Protocol):
    async def edit_html(
        self,
        *,
        html: str,
        instruction: str,
        base_revision: int,
        block_hashes: dict[str, str],
        target_block_ids: list[str] | None,
        target_kind: Literal["document", "block", "text", "image"],
        target_asset_id: str | None,
        selected_text: str | None,
        theme_id: str,
        theme_version: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> tuple[str, str]: ...

    async def edit_image(
        self,
        *,
        image: bytes,
        mime_type: str,
        filename: str,
        instruction: str,
        style_prompt: str,
        style_reference_pdf: bytes,
    ) -> bytes: ...
