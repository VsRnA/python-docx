from datetime import UTC, datetime
from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.domain.entities.document_version import DocumentVersion
from document_service.domain.value_objects.document_status import DocumentStatus


class RevisionConflictError(ValueError):
    pass


class SaveDocument:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        validator: HtmlContractValidator,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._validator = validator

    async def execute(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        base_revision: int,
        html: str,
        reason: str = "manual_edit",
    ) -> int:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        is_translation = reason.startswith("translation_")
        if document.status is not DocumentStatus.READY and not (
            is_translation and document.status is DocumentStatus.PROCESSING
        ):
            raise ValueError("Only ready documents can be edited")
        if document.current_revision != base_revision:
            raise RevisionConflictError(
                f"Expected revision {base_revision}, current revision is {document.current_revision}"
            )
        self._validator.validate(html)
        current_version = await self._versions.get_current(document_id)
        if current_version is None:
            raise ValueError("Document has no current version")
        next_revision = base_revision + 1
        document.current_revision = next_revision
        document.updated_at = datetime.now(UTC)
        saved = await self._documents.save_version_atomically(
            document,
            DocumentVersion(
                document_id=document.id,
                revision=next_revision,
                html=html,
                theme_id=current_version.theme_id,
                theme_version=current_version.theme_version,
                created_by=owner_id,
                reason=reason,
            ),
        )
        if not saved:
            raise RevisionConflictError("Document revision changed while saving")
        return next_revision
