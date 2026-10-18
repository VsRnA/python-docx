from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.application.ports.document_state_repository import DocumentCommentData
from document_service.application.services.document_operations import html_block_tree
from document_service.application.use_cases.document_state import DocumentState
from document_service.application.use_cases.get_document import GetDocument
from document_service.infrastructure.config.settings import get_settings
from document_service.presentation.api.v1.schemas.documents import (
    DocumentCommentCreateRequest,
    DocumentCommentUpdateRequest,
    DocumentSnapshotResponse,
)
from document_service.presentation.dependencies import get_current_user_id, get_session
from document_service.presentation.factories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentStateRepository,
    SqlAlchemyDocumentVersionRepository,
    TimewebS3Storage,
)

router = APIRouter(prefix="/documents")


def _state(session: AsyncSession) -> DocumentState:
    return DocumentState(SqlAlchemyDocumentRepository(session), SqlAlchemyDocumentStateRepository(session))


async def _details(session: AsyncSession, document_id: UUID, owner_id: UUID):
    settings = get_settings()
    return await GetDocument(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyDocumentVersionRepository(session),
        SqlAlchemyAssetRepository(session),
        TimewebS3Storage(settings),
    ).execute(document_id, owner_id=owner_id)


def _comment_response(item: DocumentCommentData) -> dict:
    return {
        "id": item.id,
        "block_id": item.block_id,
        "text": item.text,
        "status": item.status,
        "created_at": item.created_at,
    }


@router.get("/{document_id}/snapshot", response_model=DocumentSnapshotResponse)
async def get_document_snapshot(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
) -> DocumentSnapshotResponse:
    details = await _details(session, document_id, owner_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Document not found")
    state = await _state(session).snapshot(document_id, owner_id=owner_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Document not found")
    document, stored_snapshot, comments = state
    stored_tree = stored_snapshot.document_tree if stored_snapshot else html_block_tree(details.html)
    return DocumentSnapshotResponse(
        document_id=document_id,
        revision=document.current_revision,
        metadata={
            "title": document.title,
            "language": None,
            "style_version_id": document.style_version_id,
        },
        blocks=stored_tree.get("blocks", []),
        layout=stored_snapshot.pagination_snapshot if stored_snapshot else {},
        comments=[_comment_response(item) for item in comments],
    )


@router.post("/{document_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_document_comment(
    document_id: UUID,
    payload: DocumentCommentCreateRequest,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
) -> dict:
    item = await _state(session).add_comment(
        document_id,
        owner_id=owner_id,
        block_id=payload.block_id,
        text=payload.text,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _comment_response(item)


@router.patch("/comments/{comment_id}")
async def update_document_comment(
    comment_id: UUID,
    payload: DocumentCommentUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
) -> dict:
    item = await _state(session).update_comment(
        comment_id,
        owner_id=owner_id,
        text=payload.text,
        status=payload.status,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return _comment_response(item)
