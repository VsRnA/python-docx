from hashlib import sha256
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.application.dto.document_commands import CreateDocumentCommand
from document_service.application.errors import CodedApplicationError
from document_service.application.services.asset_ingestor import AssetIngestor
from document_service.application.services.change_set import ChangeSetConflictError
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.use_cases.create_document import CreateDocument
from document_service.application.use_cases.create_merged_document import (
    CreateMergedDocument,
    CreateMergedDocumentCommand,
    MergeUpload,
)
from document_service.application.use_cases.edit_document_with_ai import EditDocumentWithAi
from document_service.application.use_cases.export_html_preview import ExportHtmlPreview
from document_service.application.use_cases.get_document import GetDocument
from document_service.application.use_cases.list_ai_messages import ListAiMessages
from document_service.application.use_cases.list_document_versions import ListDocumentVersions
from document_service.application.use_cases.list_documents import ListDocuments
from document_service.application.use_cases.list_publications import ListPublications
from document_service.application.use_cases.publish_document import PublishDocument
from document_service.application.use_cases.restore_document_version import RestoreDocumentVersion
from document_service.application.use_cases.revoke_publication import RevokePublication
from document_service.application.use_cases.save_document import RevisionConflictError, SaveDocument
from document_service.application.use_cases.translate_document import TranslateDocument
from document_service.application.use_cases.update_document_metadata import (
    DeleteDocument,
    RenameDocument,
)
from document_service.domain.entities.asset import Asset
from document_service.domain.entities.ai_message import AiMessage
from document_service.domain.entities.ai_edit_proposal import AiEditProposal
from document_service.infrastructure.database.repositories import SqlAlchemyAiEditProposalRepository
from document_service.infrastructure.config.settings import get_settings
from document_service.presentation.api.v1.schemas.documents import (
    AiEditProposalResponse,
    AiEditAcceptRequest,
    AiEditRequest,
    AiEditResponse,
    AiMessageResponse,
    CreateDocumentResponse,
    CreateMergedDocumentResponse,
    DocumentDetailsResponse,
    DocumentListItem,
    DocumentVersionResponse,
    ExportHtmlPreviewResponse,
    PublicationListItem,
    PublishDocumentResponse,
    RenameDocumentRequest,
    RestoreVersionRequest,
    SaveDocumentResponse,
    TranslateDocumentRequest,
)
from document_service.presentation.dependencies import get_current_user_id, get_session
from document_service.presentation.factories import (
    PostgresDocumentJobQueue,
    SqlAlchemyAiMessageRepository,
    SqlAlchemyAssetRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentSourceFileRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProcessingProfileRepository,
    SqlAlchemyPublicationRepository,
    SqlAlchemyStyleRepository,
    TimewebS3Storage,
    asset_repository,
    astra_processor,
    document_repository,
    yandex_translator,
)

router = APIRouter(prefix="/documents")


@router.post("/{document_id}/assets", status_code=status.HTTP_201_CREATED)
async def upload_document_asset(
    document_id: UUID,
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
):
    document = await document_repository(session).get_owned(document_id, owner_id=owner_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    settings = get_settings()
    try:
        content = await _read_upload_limited(file, min(settings.max_docx_size_bytes, 25 * 1024 * 1024))
        AssetIngestor._validate_content(content, file.content_type or "", file.filename or "image")
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    digest = sha256(content).hexdigest()
    filename = Path(file.filename or "image").name
    mime_type = file.content_type or "application/octet-stream"
    storage = TimewebS3Storage(settings)
    stored = await storage.put(
        key=f"documents/{document_id}/assets/{digest}-{filename}",
        content=content,
        content_type=mime_type,
    )
    asset = Asset(
        document_id=document_id,
        storage_key=stored.key,
        mime_type=mime_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        filename=filename,
        alt=filename,
    )
    await asset_repository(session).add_many([asset])
    return {
        "id": str(asset.id),
        "src": f"asset://{asset.id}",
        "url": await storage.presign_get(key=stored.key),
        "filename": filename,
        "alt": asset.alt,
    }


def _html_validator() -> HtmlContractValidator:
    return HtmlContractValidator(None)


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _ai_value_error_code(error: ValueError) -> str:
    return error.code if isinstance(error, CodedApplicationError) else "validation_failed"


def _ai_conflict_error_code(error: ValueError) -> str:
    return error.code if isinstance(error, CodedApplicationError) else "revision_conflict"


async def _read_upload_limited(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > max_size_bytes:
            limit_mb = max_size_bytes / (1024 * 1024)
            raise ValueError(f"DOCX file exceeds the configured {limit_mb:g} MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=CreateDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_document(
    title: Annotated[str, Form(min_length=1, max_length=500)],
    file: Annotated[UploadFile, File()],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    style_version_id: Annotated[UUID | None, Form()] = None,
    source_language: Annotated[str | None, Form(max_length=32)] = None,
    target_language: Annotated[str | None, Form(max_length=32)] = None,
    translation_enabled: Annotated[bool, Form()] = False,
    glossary_version_id: Annotated[str | None, Form(max_length=128)] = None,
) -> CreateDocumentResponse:
    settings = get_settings()
    if style_version_id is None:
        raise HTTPException(status_code=422, detail="Select a published style before starting document processing")
    if translation_enabled and not target_language:
        raise HTTPException(status_code=422, detail="Target language is required when translation is enabled")
    if style_version_id is not None:
        published_style = await SqlAlchemyStyleRepository(session).get_published_version(
            style_version_id, owner_id=owner_id
        )
        if published_style is None:
            raise HTTPException(status_code=422, detail="Select an active published style version")
        style_settings = published_style.settings
    else:
        style_settings = {}
    try:
        content = await _read_upload_limited(file, settings.max_docx_size_bytes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)) from error
    use_case = CreateDocument(
        SqlAlchemyDocumentRepository(session),
        TimewebS3Storage(settings),
        PostgresDocumentJobQueue(),
        SqlAlchemyJobRepository(session),
        max_size_bytes=settings.max_docx_size_bytes,
        profiles=SqlAlchemyProcessingProfileRepository(session),
    )
    try:
        result = await use_case.execute(
            CreateDocumentCommand(
                title=title,
                filename=file.filename or "document.docx",
                content_type=file.content_type or "application/octet-stream",
                size_bytes=len(content),
                owner_id=owner_id,
                content=content,
                style_version_id=style_version_id,
                source_language=source_language,
                target_language=target_language,
                translation_enabled=translation_enabled,
                style_settings=style_settings,
                glossary_version_id=glossary_version_id,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return CreateDocumentResponse(document_id=result.document_id, job_id=result.job_id)


@router.post("/merge", response_model=CreateMergedDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_merged_document(
    title: Annotated[str, Form(min_length=1, max_length=500)],
    files: Annotated[list[UploadFile], File()],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    merge_notes: Annotated[str | None, Form(max_length=2000)] = None,
    style_version_id: Annotated[UUID | None, Form()] = None,
    source_language: Annotated[str | None, Form(max_length=32)] = None,
    target_language: Annotated[str | None, Form(max_length=32)] = None,
    translation_enabled: Annotated[bool, Form()] = False,
    glossary_version_id: Annotated[str | None, Form(max_length=128)] = None,
) -> CreateMergedDocumentResponse:
    settings = get_settings()
    if style_version_id is None:
        raise HTTPException(status_code=422, detail="Select a published style before starting document processing")
    if translation_enabled and not target_language:
        raise HTTPException(status_code=422, detail="Target language is required when translation is enabled")
    if style_version_id is not None:
        published_style = await SqlAlchemyStyleRepository(session).get_published_version(
            style_version_id, owner_id=owner_id
        )
        if published_style is None:
            raise HTTPException(status_code=422, detail="Select an active published style version")
        style_settings = published_style.settings
    else:
        style_settings = {}
    uploads: list[MergeUpload] = []
    try:
        for file in files:
            content = await _read_upload_limited(file, settings.max_docx_size_bytes)
            uploads.append(
                MergeUpload(
                    filename=file.filename or "document.docx",
                    content_type=file.content_type or "application/octet-stream",
                    size_bytes=len(content),
                    content=content,
                )
            )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)) from error
    use_case = CreateMergedDocument(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentSourceFileRepository(session),
        TimewebS3Storage(settings),
        PostgresDocumentJobQueue(),
        SqlAlchemyJobRepository(session),
        max_size_bytes=settings.max_docx_size_bytes,
        profiles=SqlAlchemyProcessingProfileRepository(session),
    )
    try:
        result = await use_case.execute(
            CreateMergedDocumentCommand(
                title=title,
                owner_id=owner_id,
                files=uploads,
                merge_notes=merge_notes,
                style_version_id=style_version_id,
                source_language=source_language,
                target_language=target_language,
                translation_enabled=translation_enabled,
                style_settings=style_settings,
                glossary_version_id=glossary_version_id,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return CreateMergedDocumentResponse(
        document_id=result.document_id,
        job_id=result.job_id,
        source_count=result.source_count,
    )


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
    document_status: Annotated[str | None, Query(alias="status", max_length=64)] = None,
    sort: Annotated[str, Query(pattern="^(updated|created|title)$")] = "updated",
) -> list[DocumentListItem]:
    items = await ListDocuments(SqlAlchemyDocumentRepository(session)).execute(
        owner_id=owner_id,
        limit=limit,
        offset=offset,
        search=search,
        status=document_status,
        sort=sort,
    )
    return [DocumentListItem.model_validate(item) for item in items]


@router.get("/{document_id}", response_model=DocumentDetailsResponse)
async def get_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> DocumentDetailsResponse:
    details = await GetDocument(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentVersionRepository(session),
        SqlAlchemyAssetRepository(session),
        TimewebS3Storage(get_settings()),
    ).execute(document_id, owner_id=owner_id)
    if details is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    response = DocumentDetailsResponse.model_validate(details, from_attributes=True)
    profile = await SqlAlchemyProcessingProfileRepository(session).get_latest(document_id)
    if profile is not None:
        response.processing_profile = {
            "source_language": profile.source_language,
            "target_language": profile.target_language,
            "translation_enabled": profile.translation_enabled,
            "glossary_version_id": profile.glossary_version_id,
            "status": profile.status,
        }
    return response


@router.patch("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_document(
    document_id: UUID,
    payload: RenameDocumentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    try:
        await RenameDocument(SqlAlchemyDocumentRepository(session)).execute(
            document_id=document_id,
            owner_id=owner_id,
            title=payload.title,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    try:
        await DeleteDocument(SqlAlchemyDocumentRepository(session)).execute(
            document_id=document_id,
            owner_id=owner_id,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/{document_id}/previews/html", response_model=ExportHtmlPreviewResponse)
async def export_html_preview(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ExportHtmlPreviewResponse:
    settings = get_settings()
    storage = TimewebS3Storage(settings)
    use_case = ExportHtmlPreview(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentVersionRepository(session),
        storage,
        SqlAlchemyAssetRepository(session),
    )
    try:
        key = await use_case.execute(document_id=document_id, owner_id=owner_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    expires_in = 900
    url = await storage.presign_get(key=key, expires_seconds=expires_in)
    return ExportHtmlPreviewResponse(url=url, expires_in=expires_in)


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[DocumentVersionResponse]:
    try:
        versions = await ListDocumentVersions(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
        ).execute(document_id=document_id, owner_id=owner_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [DocumentVersionResponse.model_validate(item, from_attributes=True) for item in versions]


@router.get("/{document_id}/versions/{revision}")
async def get_document_version(
    document_id: UUID,
    revision: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> dict:
    document = await SqlAlchemyDocumentRepository(session).get(document_id)
    if document is None or document.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Document not found")
    version = await SqlAlchemyDocumentVersionRepository(session).get_revision(document_id, revision)
    if version is None:
        raise HTTPException(status_code=404, detail="Revision not found")
    return {
        "revision": version.revision,
        "html": version.html,
        "reason": version.reason,
        "created_at": version.created_at,
    }


@router.post("/{document_id}/versions/restore", response_model=SaveDocumentResponse)
async def restore_document_version(
    document_id: UUID,
    payload: RestoreVersionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SaveDocumentResponse:
    try:
        revision = await RestoreDocumentVersion(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            _html_validator(),
        ).execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=payload.base_revision,
            source_revision=payload.source_revision,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return SaveDocumentResponse(revision=revision)


@router.post("/{document_id}/translations", response_model=SaveDocumentResponse)
async def translate_document(
    document_id: UUID,
    payload: TranslateDocumentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SaveDocumentResponse:
    settings = get_settings()
    translator = yandex_translator(settings)
    try:
        revision = await TranslateDocument(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            translator,
            _html_validator(),
        ).execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=payload.base_revision,
            source_language=payload.source_language,
            target_language=payload.target_language,
            glossary_version=payload.glossary_version,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return SaveDocumentResponse(revision=revision)


@router.post("/{document_id}/ai-edit-proposals", response_model=AiEditProposalResponse)
async def propose_document_ai_edit(
    document_id: UUID,
    payload: AiEditRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> AiEditProposalResponse:
    settings = get_settings()
    document = await SqlAlchemyDocumentRepository(session).get_owned(document_id, owner_id=owner_id)
    if document is None:
        raise HTTPException(status_code=404, detail=_error_detail("document_not_found", "Document not found"))
    if not payload.instruction.strip():
        raise HTTPException(status_code=422, detail=_error_detail("validation_failed", "AI edit instruction must not be empty"))
    await SqlAlchemyAiMessageRepository(session).add_many([
        AiMessage(
            document_id=document_id,
            role="user",
            content=(
                payload.instruction.strip()
                if not payload.target_block_ids
                else f"{payload.instruction.strip()}\n\nОбласть: {len(payload.target_block_ids)} блок(ов)"
            ),
            revision=payload.base_revision,
        )
    ])
    await session.commit()
    try:
        proposal = await EditDocumentWithAi(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            SqlAlchemyAssetRepository(session),
            TimewebS3Storage(settings),
            astra_processor(settings),
            _html_validator(),
        ).propose(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=payload.base_revision,
            instruction=payload.instruction,
            target_block_ids=payload.target_block_ids,
            target=payload.target.model_dump() if payload.target is not None else None,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=_error_detail("document_not_found", str(error))) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=_error_detail("revision_conflict", str(error))) from error
    except ChangeSetConflictError as error:
        raise HTTPException(
            status_code=409, detail=_error_detail(_ai_conflict_error_code(error), str(error))
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_error_detail(_ai_value_error_code(error), str(error))) from error
    stored = AiEditProposal(
        document_id=document_id,
        owner_id=owner_id,
        base_revision=proposal["base_revision"],
        summary=proposal["summary"],
        before_html=proposal["before_html"],
        after_html=proposal["after_html"],
        operations=proposal["operations"],
    )
    await SqlAlchemyAiEditProposalRepository(session).add(stored)
    await session.commit()
    return AiEditProposalResponse(proposal_id=stored.id, **proposal)


@router.post("/{document_id}/ai-edit-proposals/accept", response_model=AiEditResponse)
async def accept_document_ai_edit(
    document_id: UUID,
    payload: AiEditAcceptRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> AiEditResponse:
    try:
        proposal = await SqlAlchemyAiEditProposalRepository(session).get_owned(payload.proposal_id, owner_id)
        if proposal is None or proposal.document_id != document_id:
            raise HTTPException(status_code=404, detail=_error_detail("proposal_not_found", "AI proposal not found"))
        if proposal.status == "accepted" and proposal.accepted_revision is not None:
            return AiEditResponse(revision=proposal.accepted_revision, summary=proposal.summary)
        if proposal.status != "pending":
            raise HTTPException(status_code=409, detail=_error_detail("proposal_unavailable", "AI proposal is no longer available"))
        revision = await SaveDocument(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            _html_validator(),
        ).execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=proposal.base_revision,
            html=proposal.after_html,
            reason="ai_edit",
        )
        await SqlAlchemyAiEditProposalRepository(session).mark_accepted(proposal.id, revision)
        await SqlAlchemyAiMessageRepository(session).add_many([
            AiMessage(document_id=document_id, role="assistant", content=proposal.summary or "Изменения внесены", revision=revision),
        ])
        await session.commit()
    except LookupError as error:
        raise HTTPException(status_code=404, detail=_error_detail("document_not_found", str(error))) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=_error_detail("revision_conflict", str(error))) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_error_detail("validation_failed", str(error))) from error
    return AiEditResponse(revision=revision, summary=proposal.summary or "Изменения внесены")


@router.get("/{document_id}/ai-messages", response_model=list[AiMessageResponse])
async def list_ai_messages(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AiMessageResponse]:
    try:
        messages = await ListAiMessages(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyAiMessageRepository(session),
        ).execute(document_id=document_id, owner_id=owner_id, limit=limit)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [AiMessageResponse.model_validate(item, from_attributes=True) for item in messages]


@router.post("/{document_id}/publications", response_model=PublishDocumentResponse)
async def publish_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> PublishDocumentResponse:
    settings = get_settings()
    storage = TimewebS3Storage(settings)
    try:
        publication = await PublishDocument(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            SqlAlchemyAssetRepository(session),
            storage,
            SqlAlchemyPublicationRepository(session),
        ).execute(document_id=document_id, owner_id=owner_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    expires_in: int | None = None
    if settings.publication_base_url:
        url = f"{settings.publication_base_url.rstrip('/')}/{quote(publication.object_key)}"
    else:
        expires_in = 24 * 60 * 60
        url = await storage.presign_get(key=publication.object_key, expires_seconds=expires_in)
    return PublishDocumentResponse(
        id=publication.id,
        url=url,
        revision=publication.revision,
        expires_in=expires_in,
    )


@router.get("/{document_id}/publications", response_model=list[PublicationListItem])
async def list_publications(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[PublicationListItem]:
    settings = get_settings()
    storage = TimewebS3Storage(settings)
    try:
        publications = await ListPublications(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyPublicationRepository(session),
        ).execute(document_id=document_id, owner_id=owner_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    result: list[PublicationListItem] = []
    for publication in publications:
        expires_in: int | None = None
        if settings.publication_base_url:
            url = f"{settings.publication_base_url.rstrip('/')}/{quote(publication.object_key)}"
        else:
            expires_in = 24 * 60 * 60
            url = await storage.presign_get(key=publication.object_key, expires_seconds=expires_in)
        result.append(
            PublicationListItem(
                id=publication.id,
                revision=publication.revision,
                url="" if publication.revoked_at else url,
                expires_in=expires_in,
                created_at=publication.created_at,
                revoked_at=publication.revoked_at,
            )
        )
    return result


@router.delete("/{document_id}/publications/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_publication(
    document_id: UUID,
    publication_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    settings = get_settings()
    try:
        revoked = await RevokePublication(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyPublicationRepository(session),
            TimewebS3Storage(settings),
        ).execute(
            document_id=document_id,
            publication_id=publication_id,
            owner_id=owner_id,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not remove the published file") from error
    if not revoked:
        raise HTTPException(status_code=404, detail="Publication not found")
