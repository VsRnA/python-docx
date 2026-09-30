from uuid import UUID

from document_service.application.ports.asset_repository import AssetRepository
from document_service.application.ports.ai_message_repository import AiMessageRepository
from document_service.application.ports.document_ai_editor import DocumentAiEditor
from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.object_storage import ObjectStorage
from document_service.application.services.asset_ingestor import AssetIngestor
from document_service.application.services.change_set import ChangeSetApplier
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.use_cases.save_document import RevisionConflictError, SaveDocument
from document_service.domain.entities.ai_message import AiMessage


class EditDocumentWithAi:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        assets: AssetRepository,
        storage: ObjectStorage,
        editor: DocumentAiEditor,
        messages: AiMessageRepository,
        validator: HtmlContractValidator,
        *,
        prompt_package_version: str,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._editor = editor
        self._messages = messages
        self._validator = validator
        self._prompt_package_version = prompt_package_version
        self._changes = ChangeSetApplier()
        self._assets = AssetIngestor(assets, storage)
        self._save = SaveDocument(documents, versions, validator)

    async def execute(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        base_revision: int,
        instruction: str,
    ) -> tuple[int, str]:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        if document.current_revision != base_revision:
            raise RevisionConflictError(
                f"Expected revision {base_revision}, current revision is {document.current_revision}"
            )
        version = await self._versions.get_current(document_id)
        if version is None:
            raise ValueError("Document has no editable version")
        if not instruction.strip():
            raise ValueError("AI edit instruction must not be empty")

        change_set = await self._editor.edit(
            html=version.html,
            instruction=instruction.strip(),
            base_revision=base_revision,
            block_hashes=self._changes.block_hashes(version.html),
            prompt_package_version=self._prompt_package_version,
            theme_id=version.theme_id,
            theme_version=version.theme_version,
        )
        changed_html = self._changes.apply(
            version.html,
            change_set,
            expected_revision=base_revision,
        )
        changed_html = await self._assets.ingest(
            document_id=document_id,
            html=changed_html,
            generated_assets=change_set.assets,
        )
        self._validator.validate(changed_html)
        revision = await self._save.execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=base_revision,
            html=changed_html,
            reason="ai_edit",
        )
        await self._messages.add_many(
            [
                AiMessage(
                    document_id=document_id,
                    role="user",
                    content=instruction.strip(),
                    revision=base_revision,
                ),
                AiMessage(
                    document_id=document_id,
                    role="assistant",
                    content=change_set.summary or "Изменения внесены",
                    revision=revision,
                ),
            ]
        )
        return revision, change_set.summary
