from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from document_service.application.use_cases.get_job import GetJob
from document_service.infrastructure.database.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyJobRepository,
)
from document_service.presentation.dependencies import get_current_user_id, get_session
from document_service.infrastructure.database.models import DocumentModel, JobModel
from document_service.infrastructure.queue.celery_app import celery_app

router = APIRouter(prefix="/jobs")


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    kind: str
    status: str
    progress: int
    stage: str
    error_code: str | None
    error_message: str | None


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> JobResponse:
    job = await GetJob(
        SqlAlchemyJobRepository(session),
        SqlAlchemyDocumentRepository(session),
    ).execute(job_id, owner_id=owner_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_id: Annotated[UUID, Depends(get_current_user_id)],
) -> JobResponse:
    model = await session.scalar(
        select(JobModel)
        .join(DocumentModel, DocumentModel.id == JobModel.document_id)
        .where(JobModel.id == job_id, DocumentModel.owner_id == owner_id)
    )
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if model.status not in {"queued", "running"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is no longer active")
    was_queued = model.status == "queued"
    celery_app.control.revoke(str(job_id), terminate=not was_queued, signal="SIGTERM")
    job = await SqlAlchemyJobRepository(session).get(job_id)
    assert job is not None
    job.cancel()
    await SqlAlchemyJobRepository(session).update(job)
    document = await session.get(DocumentModel, model.document_id)
    if document is not None and document.status in {"queued", "processing"}:
        document.status = "processing_failed"
        document.processing_job_id = model.id
        await session.commit()
    return JobResponse.model_validate(job)
