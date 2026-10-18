from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.application.ports.style_repository import StyleData
from document_service.application.use_cases.manage_styles import StyleManagement
from document_service.application.use_cases.start_processing_profile import (
    StartProcessingProfile,
    StartProcessingProfileCommand,
)
from document_service.infrastructure.config.settings import get_settings
from document_service.presentation.api.v1.schemas.styles import (
    ProcessingProfileRequest,
    ProcessingProfileResponse,
    StyleCreateRequest,
    StyleDetailsResponse,
    StyleResponse,
    StyleUpdateRequest,
    StyleVersionResponse,
    StyleVersionUpdateRequest,
)
from document_service.presentation.dependencies import get_current_user_id, get_session
from document_service.presentation.factories import (
    PostgresDocumentJobQueue,
    SqlAlchemyDocumentRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProcessingProfileRepository,
    SqlAlchemyStyleRepository,
    TimewebS3Storage,
)

router = APIRouter()
MAX_STYLE_REFERENCE_SIZE_BYTES = 50 * 1024 * 1024


def style_data_response(style: StyleData, *, details: bool = False) -> StyleResponse | StyleDetailsResponse:
    current = next(
        (version for version in style.versions if version.status == "published"),
        style.versions[0] if style.versions else None,
    )
    base = StyleResponse(
        id=style.id,
        name=style.name,
        description=style.description,
        status=style.status,
        current_version=StyleVersionResponse.model_validate(current, from_attributes=True) if current else None,
        versions_count=len(style.versions),
        created_at=style.created_at,
        updated_at=style.updated_at,
    )
    if details:
        return StyleDetailsResponse(
            **base.model_dump(),
            versions=[StyleVersionResponse.model_validate(version, from_attributes=True) for version in style.versions],
        )
    return base


def style_management(session: AsyncSession) -> StyleManagement:
    settings = get_settings()
    return StyleManagement(
        SqlAlchemyStyleRepository(session),
        default_theme_id=settings.document_theme_id,
        default_theme_version=settings.document_theme_version,
    )


@router.get("/styles", response_model=list[StyleResponse])
async def list_styles(session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    styles = await style_management(session).list(owner_id)
    return [style_data_response(style) for style in styles]


@router.post("/styles/bootstrap", response_model=StyleResponse)
async def bootstrap_styles(
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    style = await manager.bootstrap(owner_id=owner_id)
    return style_data_response(style)


@router.post("/styles", response_model=StyleResponse, status_code=status.HTTP_201_CREATED)
async def create_style(
    payload: StyleCreateRequest,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    settings = {**manager.default_settings(), **payload.settings}
    style = await manager.create(
        owner_id=owner_id,
        name=payload.name,
        description=payload.description,
        settings=settings,
    )
    return style_data_response(style)


@router.get("/styles/{style_id}", response_model=StyleDetailsResponse)
async def get_style(
    style_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    style = await style_management(session).get(style_id, owner_id=owner_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    return style_data_response(style, details=True)


@router.patch("/styles/{style_id}", response_model=StyleDetailsResponse)
async def update_style(
    style_id: UUID,
    payload: StyleUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    style = await manager.get(style_id, owner_id=owner_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    try:
        if not payload.model_fields_set:
            raise ValueError("At least one style field is required")
        updated = await manager.update(
            style,
            name=payload.name,
            description=payload.description,
            prompt=payload.prompt,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return style_data_response(updated, details=True)


@router.get("/styles/{style_id}/reference")
async def get_style_reference(
    style_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    style = await manager.get(style_id, owner_id=owner_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    version = next((item for item in style.versions if item.status == "published"), None) or (style.versions[0] if style.versions else None)
    reference = version.settings.get("reference_file") if version else None
    if not isinstance(reference, dict) or not isinstance(reference.get("key"), str):
        raise HTTPException(status_code=404, detail="Style reference PDF is not attached")
    url = await TimewebS3Storage(get_settings()).presign_get(key=reference["key"])
    return {"url": url, "expires_in": 900, "filename": reference.get("filename")}


@router.post("/styles/{style_id}/reference", status_code=status.HTTP_201_CREATED)
async def upload_style_reference_for_style(
    style_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    style = await manager.get(style_id, owner_id=owner_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    version = next((item for item in style.versions if item.status == "published"), None) or (style.versions[0] if style.versions else None)
    if version is None:
        raise HTTPException(status_code=409, detail="Style has no version")
    content = await file.read(MAX_STYLE_REFERENCE_SIZE_BYTES + 1)
    if len(content) > MAX_STYLE_REFERENCE_SIZE_BYTES:
        limit_mb = MAX_STYLE_REFERENCE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Reference PDF exceeds the configured {limit_mb} MB limit")
    if file.content_type != "application/pdf" or not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="Upload a valid PDF reference")
    try:
        result = await manager.attach_reference(
            version,
            filename=file.filename or "reference.pdf",
            content=content,
            storage=TimewebS3Storage(get_settings()),
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return result


@router.post(
    "/styles/{style_id}/versions",
    response_model=StyleVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_style_version(
    style_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    style = await manager.get(style_id, owner_id=owner_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    try:
        version = await manager.create_version(style, owner_id=owner_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StyleVersionResponse.model_validate(version, from_attributes=True)


@router.delete("/styles/{style_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_style(
    style_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    style = await manager.get(style_id, owner_id=owner_id)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    await manager.delete(style)


@router.patch("/style-versions/{version_id}", response_model=StyleVersionResponse)
async def update_style_version(
    version_id: UUID,
    payload: StyleVersionUpdateRequest,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    version = await manager.get_version(version_id, owner_id=owner_id)
    if not version:
        raise HTTPException(status_code=404, detail="Style version not found")
    try:
        updated = await manager.update_version(version, payload.settings)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StyleVersionResponse.model_validate(updated, from_attributes=True)


@router.post("/style-versions/{version_id}/reference", status_code=status.HTTP_201_CREATED)
async def upload_style_reference(
    version_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    version = await manager.get_version(version_id, owner_id=owner_id)
    if not version:
        raise HTTPException(status_code=404, detail="Style version not found")
    content = await file.read(MAX_STYLE_REFERENCE_SIZE_BYTES + 1)
    if len(content) > MAX_STYLE_REFERENCE_SIZE_BYTES:
        limit_mb = MAX_STYLE_REFERENCE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Reference PDF exceeds the configured {limit_mb} MB limit")
    if file.content_type != "application/pdf" or not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="Upload a valid PDF reference")
    try:
        return await manager.attach_reference(
            version,
            filename=file.filename or "reference.pdf",
            content=content,
            storage=TimewebS3Storage(get_settings()),
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/style-versions/{version_id}/validate", response_model=StyleVersionResponse)
async def validate_style_version(
    version_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    version = await manager.get_version(version_id, owner_id=owner_id)
    if not version:
        raise HTTPException(status_code=404, detail="Style version not found")
    try:
        validated = await manager.validate(version)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StyleVersionResponse.model_validate(validated, from_attributes=True)


@router.post("/style-versions/{version_id}/publish", response_model=StyleVersionResponse)
async def publish_style_version(
    version_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    version = await manager.get_version(version_id, owner_id=owner_id)
    if not version:
        raise HTTPException(status_code=404, detail="Style version not found")
    try:
        published = await manager.publish(version)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return StyleVersionResponse.model_validate(published, from_attributes=True)


@router.post("/style-versions/{version_id}/preview")
async def preview_style_version(
    version_id: UUID,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    manager = style_management(session)
    version = await manager.get_version(version_id, owner_id=owner_id)
    if not version:
        raise HTTPException(status_code=404, detail="Style version not found")
    return await manager.preview(
        version,
        TimewebS3Storage(get_settings()),
    )


@router.post(
    "/documents/{document_id}/processing-profiles",
    response_model=ProcessingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_processing_profile(
    document_id: UUID,
    payload: ProcessingProfileRequest,
    session: AsyncSession = Depends(get_session),
    owner_id: UUID = Depends(get_current_user_id),
):
    use_case = StartProcessingProfile(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyStyleRepository(session),
        SqlAlchemyProcessingProfileRepository(session),
        SqlAlchemyJobRepository(session),
        PostgresDocumentJobQueue(),
    )
    try:
        result = await use_case.execute(
            StartProcessingProfileCommand(
                document_id=document_id,
                owner_id=owner_id,
                style_version_id=payload.style_version_id,
                source_language=payload.source_language,
                target_language=payload.target_language,
                translation_enabled=payload.translation_enabled,
                glossary_version_id=payload.glossary_version_id,
            )
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ProcessingProfileResponse.model_validate(result.profile, from_attributes=True)
