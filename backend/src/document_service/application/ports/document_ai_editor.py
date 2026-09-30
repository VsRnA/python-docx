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
    async def edit(
        self,
        *,
        html: str,
        instruction: str,
        base_revision: int,
        block_hashes: dict[str, str],
        target_block_ids: list[str] | None,
        prompt_package_version: str,
        theme_id: str,
        theme_version: str,
    ) -> DocumentChangeSet: ...
