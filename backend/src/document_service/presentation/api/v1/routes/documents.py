from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4
from pathlib import Path
from urllib.parse import quote
import re
from hashlib import sha256

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from document_service.application.dto.document_commands import CreateDocumentCommand
from document_service.application.use_cases.create_document import CreateDocument
from document_service.application.use_cases.create_merged_document import (
    CreateMergedDocument,
    CreateMergedDocumentCommand,
    MergeUpload,
)
from document_service.application.use_cases.get_document import GetDocument
from document_service.application.use_cases.list_documents import ListDocuments
from document_service.application.use_cases.export_html_preview import ExportHtmlPreview
from document_service.application.use_cases.export_pdf import ExportPdf
from document_service.application.services.html_contract import HtmlContractValidator
from document_service.application.services.asset_ingestor import AssetIngestor
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
    SqlAlchemyDocumentSourceFileRepository,
    SqlAlchemyDocumentVersionRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPublicationRepository,
    SqlAlchemyAiMessageRepository,
    SqlAlchemyProcessingProfileRepository,
)
from document_service.infrastructure.queue.celery_queue import CeleryDocumentJobQueue
from document_service.infrastructure.renderer.http_pdf_renderer import HttpPdfRenderer
from document_service.infrastructure.storage.timeweb_s3 import TimewebS3Storage
from document_service.presentation.api.v1.schemas.documents import (
    CreateDocumentResponse,
    CreateMergedDocumentResponse,
    DocumentDetailsResponse,
    DocumentVersionResponse,
    RestoreVersionRequest,
    TranslateDocumentRequest,
    AiEditRequest,
    AiEditResponse,
    AiEditProposalResponse,
    AiMessageResponse,
    PublishDocumentResponse,
    PublicationListItem,
    DocumentListItem,
    ExportHtmlPreviewResponse,
    ExportPdfResponse,
    SaveDocumentRequest,
    SaveDocumentResponse,
    RenameDocumentRequest,
    ApplyOperationsRequest,
    DocumentSnapshotResponse,
    DocumentCommentCreateRequest,
    DocumentCommentUpdateRequest,
)
from document_service.infrastructure.database.models import DocumentModel, DocumentSnapshotModel, DocumentOperationModel, DocumentCommentModel, PublicationModel, DocumentStyleModel, DocumentStyleVersionModel, ProcessingProfileModel
from document_service.domain.entities.asset import Asset
from document_service.presentation.dependencies import get_current_user_id, get_session

router = APIRouter(prefix="/documents")


@router.post("/{document_id}/assets", status_code=status.HTTP_201_CREATED)
async def upload_document_asset(
    document_id: UUID,
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
):
    document = await session.scalar(
        select(DocumentModel).where(DocumentModel.id == document_id, DocumentModel.owner_id == owner_id)
    )
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
    await SqlAlchemyAssetRepository(session).add_many([asset])
    return {
        "id": str(asset.id),
        "src": f"asset://{asset.id}",
        "url": await storage.presign_get(key=stored.key),
        "filename": filename,
        "alt": asset.alt,
    }


def _html_block_tree(html: str | None) -> dict:
    if not html:
        return {"blocks": []}
    blocks = []
    pattern = re.compile(r'<(?P<tag>p|h1|h2|h3|li|table|img|section|div)\b[^>]*data-block-id=["\'](?P<id>[^"\']+)["\'][^>]*>(?P<body>[\s\S]*?)</(?P=tag)>', re.IGNORECASE)
    for match in pattern.finditer(html):
        body = re.sub(r'<[^>]+>', ' ', match.group("body"))
        blocks.append({"id": match.group("id"), "type": match.group("tag").lower(), "text": re.sub(r'\s+', ' ', body).strip(), "html": match.group(0), "attrs": {}})
    return {"blocks": blocks}


@router.get("/{document_id}/snapshot", response_model=DocumentSnapshotResponse)
async def get_document_snapshot(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> DocumentSnapshotResponse:
    details = await GetDocument(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentVersionRepository(session),
        SqlAlchemyAssetRepository(session),
        TimewebS3Storage(get_settings()),
    ).execute(document_id, owner_id=owner_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Document not found")
    current_revision = details["current_revision"] if isinstance(details, dict) else details.current_revision
    stored_snapshot = await session.scalar(select(DocumentSnapshotModel).where(DocumentSnapshotModel.document_id == document_id, DocumentSnapshotModel.revision == current_revision))
    stored_tree = stored_snapshot.document_tree if stored_snapshot else _html_block_tree(details.html)
    return DocumentSnapshotResponse(
        document_id=document_id,
        revision=details["current_revision"] if isinstance(details, dict) else details.current_revision,
        metadata={
            "title": details["title"] if isinstance(details, dict) else details.title,
            "language": None,
            "style_version_id": details["style_version_id"] if isinstance(details, dict) else details.style_version_id,
        },
        blocks=stored_tree.get("blocks", []),
        layout=stored_snapshot.pagination_snapshot if stored_snapshot else {},
        comments=[{"id": item.id, "block_id": item.block_id, "text": item.text, "status": item.status, "created_at": item.created_at.isoformat()} for item in (await session.execute(select(DocumentCommentModel).where(DocumentCommentModel.document_id == document_id).order_by(DocumentCommentModel.created_at))).scalars()],
    )


@router.post("/{document_id}/operations")
async def apply_document_operations(
    document_id: UUID,
    payload: ApplyOperationsRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> dict:
    if not payload.operations:
        raise HTTPException(status_code=422, detail="At least one operation is required")
    supported_operations = {"insert_block", "update_block", "delete_block"}
    unsupported = {item.operation_type for item in payload.operations} - supported_operations
    if unsupported:
        raise HTTPException(status_code=422, detail={"code": "unsupported_operation", "operations": sorted(unsupported)})
    details = await GetDocument(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentVersionRepository(session),
        SqlAlchemyAssetRepository(session),
        TimewebS3Storage(get_settings()),
    ).execute(document_id, owner_id=owner_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Document not found")
    current_revision = details["current_revision"] if isinstance(details, dict) else details.current_revision
    supplied_ids = [item.operation_id for item in payload.operations if item.operation_id is not None]
    if len(supplied_ids) != len(payload.operations) or len(set(supplied_ids)) != len(supplied_ids):
        raise HTTPException(status_code=422, detail="Each operation requires a unique operation_id")
    previous_operations = list((await session.execute(
        select(DocumentOperationModel).where(DocumentOperationModel.id.in_(supplied_ids))
    )).scalars())
    if previous_operations:
        by_id = {item.id: item for item in previous_operations}
        same_request = len(by_id) == len(payload.operations) and all(
            item.operation_id in by_id
            and by_id[item.operation_id].document_id == document_id
            and by_id[item.operation_id].operation_type == item.operation_type
            and by_id[item.operation_id].block_id == item.block_id
            and by_id[item.operation_id].payload == item.payload
            for item in payload.operations
        )
        if same_request:
            return {"revision": max(item.resulting_revision for item in previous_operations), "accepted_operations": [str(item.operation_id) for item in payload.operations]}
        raise HTTPException(status_code=409, detail="Operation id has already been used")
    if current_revision != payload.base_revision:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": "Document revision changed"})
    next_revision = current_revision + 1
    now = datetime.now(timezone.utc)
    snapshot = await session.scalar(select(DocumentSnapshotModel).where(DocumentSnapshotModel.document_id == document_id, DocumentSnapshotModel.revision == current_revision))
    if snapshot is None:
        current_html = details["html"] if isinstance(details, dict) else details.html
        snapshot = DocumentSnapshotModel(id=uuid4(), document_id=document_id, revision=current_revision, document_tree=_html_block_tree(current_html), pagination_snapshot={}, created_at=now)
        session.add(snapshot)
    tree = dict(snapshot.document_tree or {})
    blocks = [dict(block) for block in tree.get("blocks", [])]
    for operation in payload.operations:
        if operation.operation_type == "delete_block":
            if not any(block.get("id") == operation.block_id for block in blocks):
                raise HTTPException(status_code=422, detail=f"Block {operation.block_id} was not found")
            blocks = [block for block in blocks if block.get("id") != operation.block_id]
        elif operation.operation_type == "insert_block":
            block = dict(operation.payload)
            block.setdefault("id", operation.block_id)
            if block.get("id") != operation.block_id or not isinstance(block.get("html"), str):
                raise HTTPException(status_code=422, detail="Inserted blocks require matching id and HTML")
            if any(existing.get("id") == operation.block_id for existing in blocks):
                raise HTTPException(status_code=409, detail="Block id already exists")
            blocks.append(block)
        elif operation.operation_type == "update_block":
            matched = next((block for block in blocks if block.get("id") == operation.block_id), None)
            if matched is None:
                raise HTTPException(status_code=422, detail=f"Block {operation.block_id} was not found")
            if not isinstance(operation.payload.get("html"), str):
                raise HTTPException(status_code=422, detail="Updated blocks require HTML")
            matched.update(operation.payload)
        session.add(DocumentOperationModel(id=operation.operation_id or uuid4(), document_id=document_id, base_revision=payload.base_revision, resulting_revision=next_revision, operation_type=operation.operation_type, block_id=operation.block_id, payload=operation.payload, created_at=now))
    tree["blocks"] = blocks
    updated_html = "".join(block.get("html", "") for block in blocks)
    try:
        next_revision = await SaveDocument(
            SqlAlchemyDocumentRepository(session),
            SqlAlchemyDocumentVersionRepository(session),
            _html_validator(),
        ).execute(
            document_id=document_id,
            owner_id=owner_id,
            base_revision=current_revision,
            html=updated_html,
            reason="document_operations",
        )
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "revision_conflict", "message": str(error)}) from error
    except (ValueError, LookupError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    session.add(DocumentSnapshotModel(id=uuid4(), document_id=document_id, revision=next_revision, document_tree=tree, pagination_snapshot=snapshot.pagination_snapshot, created_at=now))
    await session.commit()
    return {"revision": next_revision, "accepted_operations": [str(operation.operation_id) for operation in payload.operations]}


@router.get("/{document_id}/operations")
async def get_document_operations(document_id: UUID, session: Annotated[AsyncSession, Depends(get_session)], owner_id: Annotated[UUID, Depends(get_current_user_id)], after: int = 0) -> dict:
    details = await GetDocument(SqlAlchemyDocumentRepository(session), SqlAlchemyDocumentVersionRepository(session), SqlAlchemyAssetRepository(session), TimewebS3Storage(get_settings())).execute(document_id, owner_id=owner_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Document not found")
    operations = list((await session.execute(select(DocumentOperationModel).where(DocumentOperationModel.document_id == document_id, DocumentOperationModel.resulting_revision > after).order_by(DocumentOperationModel.created_at))).scalars())
    return {
        "revision": details.current_revision,
        "operations": [
            {
                "operation_id": str(item.id),
                "operation_type": item.operation_type,
                "block_id": item.block_id,
                "payload": item.payload,
            }
            for item in operations
        ],
    }


@router.post("/{document_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_document_comment(document_id: UUID, payload: DocumentCommentCreateRequest, session: Annotated[AsyncSession, Depends(get_session)], owner_id: Annotated[UUID, Depends(get_current_user_id)]) -> dict:
    details = await GetDocument(SqlAlchemyDocumentRepository(session), SqlAlchemyDocumentVersionRepository(session), SqlAlchemyAssetRepository(session), TimewebS3Storage(get_settings())).execute(document_id, owner_id=owner_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Document not found")
    item = DocumentCommentModel(id=uuid4(), document_id=document_id, block_id=payload.block_id, text=payload.text, status="open", created_at=datetime.now(timezone.utc))
    session.add(item)
    await session.commit()
    return {"id": item.id, "block_id": item.block_id, "text": item.text, "status": item.status, "created_at": item.created_at}


@router.patch("/comments/{comment_id}")
async def update_document_comment(comment_id: UUID, payload: DocumentCommentUpdateRequest, session: Annotated[AsyncSession, Depends(get_session)], owner_id: Annotated[UUID, Depends(get_current_user_id)]) -> dict:
    item = await session.scalar(select(DocumentCommentModel).join(DocumentModel, DocumentModel.id == DocumentCommentModel.document_id).where(DocumentCommentModel.id == comment_id, DocumentModel.owner_id == owner_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if payload.text is not None:
        item.text = payload.text
    if payload.status is not None:
        item.status = payload.status
    await session.commit()
    return {"id": item.id, "block_id": item.block_id, "text": item.text, "status": item.status, "created_at": item.created_at}


def _html_validator() -> HtmlContractValidator:
    settings = get_settings()
    classes_path = Path(settings.prompt_root) / settings.prompt_package_version / "classes.txt"
    return HtmlContractValidator(set(classes_path.read_text(encoding="utf-8").splitlines()))


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _ai_value_error_code(message: str) -> str:
    if message.startswith("Selected blocks were not found"):
        return "selection_not_found"
    if message == "AI edit changed blocks outside the selected area":
        return "outside_selected_area"
    if "change set" in message.lower():
        return "invalid_change_set"
    if "contract" in message.lower() or "html" in message.lower():
        return "validation_failed"
    return "validation_failed"


def _ai_conflict_error_code(message: str) -> str:
    if message.startswith("Block not found"):
        return "selection_not_found"
    if message.startswith("Block changed"):
        return "block_changed"
    if "change set" in message.lower():
        return "invalid_change_set"
    return "revision_conflict"


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
        published_style = await session.scalar(
            select(DocumentStyleVersionModel)
            .join(DocumentStyleModel)
            .where(
                DocumentStyleVersionModel.id == style_version_id,
                DocumentStyleVersionModel.status == "published",
                DocumentStyleModel.owner_id == owner_id,
                DocumentStyleModel.status == "active",
            )
        )
        if published_style is None:
            raise HTTPException(status_code=422, detail="Select an active published style version")
        style_settings = published_style.settings or {}
    else:
        style_settings = {}
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
        published_style = await session.scalar(
            select(DocumentStyleVersionModel)
            .join(DocumentStyleModel)
            .where(
                DocumentStyleVersionModel.id == style_version_id,
                DocumentStyleVersionModel.status == "published",
                DocumentStyleModel.owner_id == owner_id,
                DocumentStyleModel.status == "active",
            )
        )
        if published_style is None:
            raise HTTPException(status_code=422, detail="Select an active published style version")
        style_settings = published_style.settings or {}
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
        CeleryDocumentJobQueue(),
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
        owner_id=owner_id, limit=limit, offset=offset, search=search, status=document_status, sort=sort
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
    profile = await session.scalar(
        select(ProcessingProfileModel)
        .where(ProcessingProfileModel.document_id == document_id)
        .order_by(ProcessingProfileModel.created_at.desc())
    )
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
    return {"revision": version.revision, "html": version.html, "reason": version.reason, "created_at": version.created_at}


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("document_not_found", str(error)),
        ) from error
    except RevisionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail("revision_conflict", str(error)),
        ) from error
    except ChangeSetConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail(_ai_conflict_error_code(str(error)), str(error)),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error_detail(_ai_value_error_code(str(error)), str(error)),
        ) from error
    return AiEditResponse(revision=revision, summary=summary)


@router.post("/{document_id}/ai-edit-proposals", response_model=AiEditProposalResponse)
async def propose_document_ai_edit(
    document_id: UUID,
    payload: AiEditRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> AiEditProposalResponse:
    settings = get_settings()
    try:
        proposal = await EditDocumentWithAi(
            SqlAlchemyDocumentRepository(session), SqlAlchemyDocumentVersionRepository(session), SqlAlchemyAssetRepository(session),
            TimewebS3Storage(settings), OpenAIAstraDocumentProcessor(settings, Path(settings.prompt_root)),
            SqlAlchemyAiMessageRepository(session), _html_validator(), prompt_package_version=settings.prompt_package_version,
        ).propose(document_id=document_id, owner_id=owner_id, base_revision=payload.base_revision, instruction=payload.instruction, target_block_ids=payload.target_block_ids)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=_error_detail("document_not_found", str(error))) from error
    except RevisionConflictError as error:
        raise HTTPException(status_code=409, detail=_error_detail("revision_conflict", str(error))) from error
    except ChangeSetConflictError as error:
        raise HTTPException(status_code=409, detail=_error_detail(_ai_conflict_error_code(str(error)), str(error))) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=_error_detail(_ai_value_error_code(str(error)), str(error))) from error
    return AiEditProposalResponse.model_validate(proposal)


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
    publication = await session.scalar(
        select(PublicationModel)
        .join(DocumentModel, DocumentModel.id == PublicationModel.document_id)
        .where(
            PublicationModel.id == publication_id,
            PublicationModel.document_id == document_id,
            DocumentModel.owner_id == owner_id,
        )
    )
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    if publication.revoked_at is not None:
        return
    try:
        await TimewebS3Storage(get_settings()).delete(key=publication.object_key)
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not remove the published file") from error
    publication.revoked_at = datetime.now(timezone.utc)
    await session.commit()
