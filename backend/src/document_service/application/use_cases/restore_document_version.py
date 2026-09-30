from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.use_cases.save_document import RevisionConflictError, SaveDocument


class RestoreDocumentVersion:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        validator: HtmlContractValidator,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._save = SaveDocument(documents, versions, validator)

    async def execute(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        base_revision: int,
        source_revision: int,
    ) -> int:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        if document.current_revision != base_revision:
            raise RevisionConflictError(
                f"Expected revision {base_revision}, current revision is {document.current_revision}"
            )
        source = await self._versions.get_revision(document_id, source_revision)
        if source is None:
            raise LookupError("Source revision not found")
        return await self._save.execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=base_revision,
            html=source.html,
            reason=f"restore_revision_{source_revision}",
        )
