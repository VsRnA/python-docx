from uuid import UUID

from document_service.application.ports.document_repository import DocumentRepository
from document_service.application.ports.document_version_repository import DocumentVersionRepository
from document_service.application.ports.translator import Translator
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.services.html_translation import HtmlTranslationMapper
from document_service.application.use_cases.save_document import RevisionConflictError, SaveDocument


class TranslateDocument:
    def __init__(
        self,
        documents: DocumentRepository,
        versions: DocumentVersionRepository,
        translator: Translator,
        validator: HtmlContractValidator,
    ) -> None:
        self._documents = documents
        self._versions = versions
        self._translator = translator
        self._mapper = HtmlTranslationMapper()
        self._save = SaveDocument(documents, versions, validator)

    async def execute(
        self,
        *,
        document_id: UUID,
        owner_id: UUID,
        base_revision: int,
        source_language: str,
        target_language: str,
        glossary_version: str | None = None,
    ) -> int:
        document = await self._documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            raise LookupError("Document not found")
        if document.current_revision != base_revision:
            raise RevisionConflictError(
                f"Expected revision {base_revision}, current revision is {document.current_revision}"
            )
        version = await self._versions.get_current(document_id)
        if version is None:
            raise ValueError("Document has no translatable version")
        extracted = self._mapper.extract(version.html)
        translated = await self._translator.translate(
            extracted.segments,
            source_language=source_language,
            target_language=target_language,
            glossary_version=glossary_version,
        )
        translated_html = self._mapper.merge(extracted, translated)
        return await self._save.execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=base_revision,
            html=translated_html,
            reason=f"translation_{source_language}_to_{target_language}",
        )
