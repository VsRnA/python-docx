from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.application.use_cases.get_job import GetJob
from document_service.infrastructure.database.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyJobRepository,
)
from document_service.presentation.dependencies import get_current_user_id, get_session

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
