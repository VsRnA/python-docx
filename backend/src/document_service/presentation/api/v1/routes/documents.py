from typing import Annotated
from uuid import UUID
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.application.dto.document_commands import CreateDocumentCommand
from document_service.application.use_cases.create_document import CreateDocument
from document_service.application.use_cases.get_document import GetDocument
from document_service.application.use_cases.list_documents import ListDocuments
from document_service.application.use_cases.export_pdf import ExportPdf
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.use_cases.save_document import RevisionConflictError, SaveDocument
from document_service.application.use_cases.edit_document_with_ai import EditDocumentWithAi
from document_service.application.use_cases.list_document_versions import ListDocumentVersions
from document_service.application.use_cases.publish_document import PublishDocument
from document_service.application.use_cases.list_publications import ListPublications
from document_service.application.use_cases.list_ai_messages import ListAiMessages
from document_service.application.use_cases.restore_document_version import RestoreDocumentVersion
from document_service.application.use_cases.translate_document import TranslateDocument
from document_service.application.use_cases.update_document_metadata import DeleteDocument, RenameDocument
from document_service.application.services.change_set import ChangeSetConflictError
from document_service.infrastructure.ai.astra_processor import OpenAIAstraDocumentProcessor
from document_service.infrastructure.ai.yandex_translator import YandexGPTTranslator
from document_service.infrastructure.config.settings import get_settings
from document_service.infrastructure.database.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPublicationRepository,
    SqlAlchemyAiMessageRepository,
)
from document_service.infrastructure.queue.celery_queue import CeleryDocumentJobQueue
from document_service.infrastructure.renderer.http_pdf_renderer import HttpPdfRenderer
from document_service.infrastructure.storage.timeweb_s3 import TimewebS3Storage
from document_service.presentation.api.v1.schemas.documents import (
    CreateDocumentResponse,
    DocumentDetailsResponse,
    DocumentVersionResponse,
    RestoreVersionRequest,
    TranslateDocumentRequest,
    AiEditRequest,
    AiEditResponse,
    AiMessageResponse,
    PublishDocumentResponse,
    PublicationListItem,
    DocumentListItem,
    ExportPdfResponse,
    SaveDocumentRequest,
    SaveDocumentResponse,
    RenameDocumentRequest,
)
from document_service.presentation.dependencies import get_current_user_id, get_session

router = APIRouter(prefix="/documents")


def _html_validator() -> HtmlContractValidator:
    settings = get_settings()
    classes_path = Path(settings.prompt_root) / settings.prompt_package_version / "classes.txt"
    return HtmlContractValidator(set(classes_path.read_text(encoding="utf-8").splitlines()))


async def _read_upload_limited(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > max_size_bytes:
            raise ValueError("DOCX file exceeds the 50 MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("", response_model=CreateDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_document(
    title: Annotated[str, Form(min_length=1, max_length=500)],
    file: Annotated[UploadFile, File()],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreateDocumentResponse:
    settings = get_settings()
    try:
        content = await _read_upload_limited(file, settings.max_docx_size_bytes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)) from error
    use_case = CreateDocument(
        SqlAlchemyDocumentRepository(session),
        TimewebS3Storage(settings),
        CeleryDocumentJobQueue(),
        SqlAlchemyJobRepository(session),
        max_size_bytes=settings.max_docx_size_bytes,
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
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return CreateDocumentResponse(document_id=result.document_id, job_id=result.job_id)


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentListItem]:
    items = await ListDocuments(SqlAlchemyDocumentRepository(session)).execute(
        owner_id=owner_id, limit=limit, offset=offset
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
    return DocumentDetailsResponse.model_validate(details, from_attributes=True)


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


@router.put("/{document_id}/content", response_model=SaveDocumentResponse)
async def save_document(
    document_id: UUID,
    payload: SaveDocumentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SaveDocumentResponse:
    use_case = SaveDocument(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentVersionRepository(session),
        _html_validator(),
    )
    try:
        revision = await use_case.execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=payload.base_revision,
            html=payload.html,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return SaveDocumentResponse(revision=revision)


@router.post("/{document_id}/exports/pdf", response_model=ExportPdfResponse)
async def export_pdf(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ExportPdfResponse:
    settings = get_settings()
    storage = TimewebS3Storage(settings)
    use_case = ExportPdf(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentVersionRepository(session),
        storage,
        HttpPdfRenderer(settings.renderer_url),
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
    return ExportPdfResponse(url=url, expires_in=expires_in)


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
    translator = YandexGPTTranslator(
        api_key=settings.yandex_gpt_api_key,
        folder_id=settings.yandex_folder_id,
        model_uri=settings.yandex_model_uri,
    )
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


@router.post("/{document_id}/ai-edits", response_model=AiEditResponse)
async def edit_document_with_ai(
    document_id: UUID,
    payload: AiEditRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> AiEditResponse:
    settings = get_settings()
    storage = TimewebS3Storage(settings)
    try:
        revision, summary = await EditDocumentWithAi(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            SqlAlchemyAssetRepository(session),
            storage,
            OpenAIAstraDocumentProcessor(settings, Path(settings.prompt_root)),
            SqlAlchemyAiMessageRepository(session),
            _html_validator(),
            prompt_package_version=settings.prompt_package_version,
        ).execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=payload.base_revision,
            instruction=payload.instruction,
            target_block_ids=payload.target_block_ids,
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (RevisionConflictError, ChangeSetConflictError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    return AiEditResponse(revision=revision, summary=summary)


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
            HttpPdfRenderer(settings.renderer_url),
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
                url=url,
                expires_in=expires_in,
                created_at=publication.created_at,
            )
        )
    return result
