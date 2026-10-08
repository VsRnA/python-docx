from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID, uuid4
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import re
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.infrastructure.database.models import DocumentModel, DocumentStyleModel, DocumentStyleVersionModel, ProcessingProfileModel
from document_service.infrastructure.config.settings import get_settings
from document_service.infrastructure.renderer.http_pdf_renderer import HttpPdfRenderer
from document_service.infrastructure.storage.timeweb_s3 import TimewebS3Storage
from document_service.presentation.api.v1.schemas.styles import (
    ProcessingProfileRequest, ProcessingProfileResponse, StyleCreateRequest,
    StyleDetailsResponse, StyleResponse, StyleVersionResponse, StyleVersionUpdateRequest,
)
from document_service.presentation.dependencies import get_current_user_id, get_session
from document_service.infrastructure.queue.celery_queue import CeleryDocumentJobQueue
from document_service.infrastructure.database.repositories import SqlAlchemyJobRepository
from document_service.domain.entities.job import Job
from document_service.application.services.style_theme import SUPPORTED_RENDERER_THEMES, resolve_renderer_theme

router = APIRouter()


def _version(model: DocumentStyleVersionModel) -> StyleVersionResponse:
    return StyleVersionResponse.model_validate(model, from_attributes=True)


def _default_style_settings() -> dict:
    settings = get_settings()
    return {
        "page": "A4, portrait",
        "font": "Lato",
        "accent": "#F67828",
        "margins": "24 / 13 / 18 мм",
        "renderer_theme_id": settings.document_theme_id,
        "renderer_theme_version": settings.document_theme_version,
    }


async def _style_response(session: AsyncSession, style: DocumentStyleModel, details: bool = False):
    versions = list((await session.execute(select(DocumentStyleVersionModel).where(DocumentStyleVersionModel.style_id == style.id).order_by(DocumentStyleVersionModel.version.desc()))).scalars())
    current = next((item for item in versions if item.status == "published"), versions[0] if versions else None)
    documents_count = await session.scalar(select(func.count(ProcessingProfileModel.id)).join(DocumentStyleVersionModel, ProcessingProfileModel.style_version_id == DocumentStyleVersionModel.id).where(DocumentStyleVersionModel.style_id == style.id))
    base = StyleResponse(
        id=style.id, name=style.name, description=style.description, status=style.status,
        current_version=_version(current) if current else None, versions_count=len(versions),
        documents_count=documents_count or 0, created_at=style.created_at, updated_at=style.updated_at,
    )
    if details:
        return StyleDetailsResponse(**base.model_dump(), versions=[_version(item) for item in versions])
    return base


@router.get("/styles", response_model=list[StyleResponse])
async def list_styles(session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    styles = list((await session.execute(select(DocumentStyleModel).where(DocumentStyleModel.owner_id == owner_id).order_by(DocumentStyleModel.updated_at.desc()))).scalars())
    if not any(
        version.status == "published"
        for version in (await session.execute(
            select(DocumentStyleVersionModel)
            .join(DocumentStyleModel)
            .where(DocumentStyleModel.owner_id == owner_id)
        )).scalars()
    ):
        # Make the renderer's existing project theme an explicit, versioned style
        # instead of leaving new workspaces with no selectable published style.
        base_settings = get_settings()
        style_id = uuid4()
        now = datetime.now(timezone.utc)
        style_settings = _default_style_settings()
        manifest = {
            "settings": style_settings,
            "renderer_theme": {
                "id": base_settings.document_theme_id,
                "version": base_settings.document_theme_version,
            },
            "schema_version": "1",
        }
        version = DocumentStyleVersionModel(
            id=uuid4(),
            style_id=style_id,
            version=1,
            status="published",
            manifest=manifest,
            manifest_sha256=sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            settings=style_settings,
            validation_report={"status": "passed", "errors": [], "warnings": []},
            created_by=owner_id,
            created_at=now,
            published_at=now,
        )
        style = DocumentStyleModel(
            id=style_id,
            name="Стандарт проекта · A4",
            description="Базовая стилизация проекта на основе встроенной темы оформления.",
            owner_id=owner_id,
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add_all([style, version])
        await session.commit()
        styles.append(style)
    return [await _style_response(session, style) for style in styles]


@router.post("/styles", response_model=StyleResponse, status_code=status.HTTP_201_CREATED)
async def create_style(payload: StyleCreateRequest, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    now = datetime.now(timezone.utc)
    style = DocumentStyleModel(id=uuid4(), name=payload.name, description=payload.description, owner_id=owner_id, status="active", created_at=now, updated_at=now)
    style_settings = {**_default_style_settings(), **payload.settings}
    manifest = {"settings": style_settings, "renderer_theme": {"id": style_settings["renderer_theme_id"], "version": style_settings["renderer_theme_version"]}, "schema_version": "1"}
    version = DocumentStyleVersionModel(id=uuid4(), style_id=style.id, version=1, status="draft", manifest=manifest, manifest_sha256=sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(), settings=style_settings, validation_report=None, created_by=owner_id, created_at=now)
    session.add_all([style, version])
    await session.commit()
    return await _style_response(session, style)


@router.get("/styles/{style_id}", response_model=StyleDetailsResponse)
async def get_style(style_id: UUID, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    style = await session.scalar(select(DocumentStyleModel).where(DocumentStyleModel.id == style_id, DocumentStyleModel.owner_id == owner_id))
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    return await _style_response(session, style, details=True)


@router.post("/styles/{style_id}/versions", response_model=StyleVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_style_version(style_id: UUID, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    style = await session.scalar(select(DocumentStyleModel).where(DocumentStyleModel.id == style_id, DocumentStyleModel.owner_id == owner_id))
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    if style.status != "active":
        raise HTTPException(status_code=409, detail="Archived styles cannot create new versions")
    latest = await session.scalar(select(DocumentStyleVersionModel).where(DocumentStyleVersionModel.style_id == style_id).order_by(DocumentStyleVersionModel.version.desc()))
    now = datetime.now(timezone.utc)
    version = DocumentStyleVersionModel(id=uuid4(), style_id=style_id, version=(latest.version + 1 if latest else 1), status="draft", manifest=latest.manifest if latest else {}, manifest_sha256=latest.manifest_sha256 if latest else "", settings=latest.settings.copy() if latest else {}, validation_report=None, created_by=owner_id, created_at=now)
    style.updated_at = now
    session.add(version)
    await session.commit()
    return _version(version)


@router.post("/styles/{style_id}/duplicate", response_model=StyleResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_style(style_id: UUID, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    source = await session.scalar(select(DocumentStyleModel).where(DocumentStyleModel.id == style_id, DocumentStyleModel.owner_id == owner_id))
    if not source:
        raise HTTPException(status_code=404, detail="Style not found")
    source_version = await session.scalar(select(DocumentStyleVersionModel).where(DocumentStyleVersionModel.style_id == style_id).order_by(DocumentStyleVersionModel.version.desc()))
    now = datetime.now(timezone.utc)
    copy_style = DocumentStyleModel(id=uuid4(), name=f"{source.name} — копия", description=source.description, owner_id=owner_id, status="active", created_at=now, updated_at=now)
    copy_version = DocumentStyleVersionModel(id=uuid4(), style_id=copy_style.id, version=1, status="draft", manifest=dict(source_version.manifest) if source_version else {}, manifest_sha256=source_version.manifest_sha256 if source_version else "", settings=dict(source_version.settings) if source_version else {}, validation_report=None, created_by=owner_id, created_at=now)
    session.add_all([copy_style, copy_version])
    await session.commit()
    return await _style_response(session, copy_style)


@router.post("/styles/{style_id}/archive", response_model=StyleResponse)
async def archive_style(style_id: UUID, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    style = await session.scalar(select(DocumentStyleModel).where(DocumentStyleModel.id == style_id, DocumentStyleModel.owner_id == owner_id))
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    style.status = "archived"
    await session.execute(DocumentStyleVersionModel.__table__.update().where(DocumentStyleVersionModel.style_id == style_id, DocumentStyleVersionModel.status == "draft").values(status="archived"))
    await session.commit()
    return await _style_response(session, style)


@router.patch("/style-versions/{version_id}", response_model=StyleVersionResponse)
async def update_style_version(version_id: UUID, payload: StyleVersionUpdateRequest, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    version = await session.scalar(select(DocumentStyleVersionModel).join(DocumentStyleModel).where(DocumentStyleVersionModel.id == version_id, DocumentStyleModel.owner_id == owner_id))
    if not version or version.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft style versions can be edited")
    version.settings = payload.settings
    version.manifest = {
        "settings": payload.settings,
        "renderer_theme": {
            "id": payload.settings.get("renderer_theme_id", get_settings().document_theme_id),
            "version": payload.settings.get("renderer_theme_version", get_settings().document_theme_version),
        },
        "schema_version": "1",
    }
    version.manifest_sha256 = sha256(json.dumps(version.manifest, sort_keys=True).encode()).hexdigest()
    version.validation_report = None
    await session.commit()
    return _version(version)


@router.post("/style-versions/{version_id}/reference", status_code=status.HTTP_201_CREATED)
async def upload_style_reference(version_id: UUID, file: UploadFile = File(...), session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    version = await session.scalar(select(DocumentStyleVersionModel).join(DocumentStyleModel).where(DocumentStyleVersionModel.id == version_id, DocumentStyleModel.owner_id == owner_id))
    if not version or version.status != "draft":
        raise HTTPException(status_code=409, detail="A reference can only be attached to a draft style version")
    content = await file.read(25 * 1024 * 1024 + 1)
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Reference PDF exceeds the 25 MB limit")
    if file.content_type != "application/pdf" or not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="Upload a valid PDF reference")
    settings = get_settings()
    digest = sha256(content).hexdigest()
    filename = Path(file.filename or "reference.pdf").name
    stored = await TimewebS3Storage(settings).put(
        key=f"styles/{version.style_id}/versions/{version.version}/reference/{digest}-{filename}",
        content=content,
        content_type="application/pdf",
    )
    version.settings = {**(version.settings or {}), "reference_file": {"key": stored.key, "filename": filename, "sha256": digest}}
    version.manifest = {"settings": version.settings, "schema_version": "1"}
    version.manifest_sha256 = sha256(json.dumps(version.manifest, sort_keys=True).encode()).hexdigest()
    version.validation_report = None
    await session.commit()
    return {"filename": filename, "sha256": digest, "size_bytes": stored.size_bytes}


@router.post("/style-versions/{version_id}/validate", response_model=StyleVersionResponse)
async def validate_style_version(version_id: UUID, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    version = await session.scalar(select(DocumentStyleVersionModel).join(DocumentStyleModel).where(DocumentStyleVersionModel.id == version_id, DocumentStyleModel.owner_id == owner_id))
    if not version:
        raise HTTPException(status_code=404, detail="Style version not found")
    if version.status not in {"draft", "validating"}:
        raise HTTPException(status_code=409, detail="Only a draft style version can be validated")
    version.status = "validating"
    errors = []
    warnings = []
    page = version.settings.get("page", "A4, portrait")
    if not isinstance(page, str) or not re.fullmatch(r"\s*(A4|A5|Letter)\s*(?:,\s*(portrait|landscape))?\s*", page, re.IGNORECASE):
        errors.append("Формат страницы должен быть A4, A5 или Letter с ориентацией portrait/landscape")
    font = version.settings.get("font", "Lato")
    if font not in {"Lato", "Arial", "Helvetica", "Inter"}:
        errors.append("Выбран неподдерживаемый шрифт")
    accent = version.settings.get("accent", "#F67828")
    if not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        errors.append("Цвет акцента должен быть в формате #RRGGBB")
    margins = version.settings.get("margins", "24 / 13 / 18 мм")
    margin_values = re.findall(r"\d+(?:\.\d+)?", margins) if isinstance(margins, str) else []
    if len(margin_values) != 3 or not all(8 <= float(value) <= 40 for value in margin_values):
        errors.append("Поля задаются тремя значениями от 8 до 40 мм")
    if not version.settings:
        warnings.append("Параметры стилизации не заполнены; будут использованы значения темы по умолчанию")
    if not version.manifest_sha256:
        errors.append("Не сформирован manifest")
    theme_settings = get_settings()
    renderer_theme = (
        version.settings.get("renderer_theme_id", theme_settings.document_theme_id),
        version.settings.get("renderer_theme_version", theme_settings.document_theme_version),
    )
    if renderer_theme not in SUPPORTED_RENDERER_THEMES:
        errors.append("Выбрана неподдерживаемая тема renderer")
        renderer_theme = (theme_settings.document_theme_id, theme_settings.document_theme_version)
    if not errors:
        try:
            rendered_pdf = await HttpPdfRenderer(get_settings().renderer_url).render(
                html="<article class='manual'><h1>Проверка стилизации</h1><p>Тест renderer перед публикацией.</p></article>",
                title="Style validation",
                theme_id=renderer_theme[0],
                theme_version=renderer_theme[1],
                style_settings=version.settings,
            )
            if not rendered_pdf.startswith(b"%PDF-"):
                errors.append("Renderer вернул файл, который не является PDF")
        except Exception as error:
            errors.append(f"Тестовый PDF не сформирован: {type(error).__name__}")
    version.validation_report = {"status": "failed" if errors else "passed", "errors": errors, "warnings": warnings}
    if errors:
        version.status = "draft"
    await session.commit()
    return _version(version)


@router.post("/style-versions/{version_id}/publish", response_model=StyleVersionResponse)
async def publish_style_version(version_id: UUID, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    version = await session.scalar(select(DocumentStyleVersionModel).join(DocumentStyleModel).where(DocumentStyleVersionModel.id == version_id, DocumentStyleModel.owner_id == owner_id))
    if not version or version.status != "validating":
        raise HTTPException(status_code=409, detail="Validate the style version before publishing")
    await session.execute(DocumentStyleVersionModel.__table__.update().where(DocumentStyleVersionModel.style_id == version.style_id, DocumentStyleVersionModel.status == "published").values(status="archived"))
    version.status = "published"
    version.published_at = datetime.now(timezone.utc)
    await session.commit()
    return _version(version)


@router.post("/style-versions/{version_id}/preview")
async def preview_style_version(version_id: UUID, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    version = await session.scalar(select(DocumentStyleVersionModel).join(DocumentStyleModel).where(DocumentStyleVersionModel.id == version_id, DocumentStyleModel.owner_id == owner_id))
    if not version:
        raise HTTPException(status_code=404, detail="Style version not found")
    settings = version.settings or {}
    html = '''<article class="manual">
      <header class="manual-header"><span class="manual-header__title">Руководство по эксплуатации</span></header>
      <h1 class="manual-heading--h1">Пример документа</h1>
      <p class="manual-paragraph">Так будет выглядеть основной текст документа в выбранной стилизации.</p>
      <h2 class="manual-heading--h2">Заголовок раздела</h2>
      <aside class="manual-warning"><strong class="manual-warning__title">Внимание</strong><p>Пример предупреждения и компонента документа.</p></aside>
    </article>'''
    theme_settings = get_settings()
    theme_id, theme_version = resolve_renderer_theme(
        settings, theme_settings.document_theme_id, theme_settings.document_theme_version
    )
    rendered = await HttpPdfRenderer(theme_settings.renderer_url).bundle_html(html=html, title="Style preview", theme_id=theme_id, theme_version=theme_version, style_settings=settings)
    storage = TimewebS3Storage(get_settings())
    stored = await storage.put(key=f"style-previews/{version.id}/{version.version}.html", content=rendered, content_type="text/html")
    return {"url": await storage.presign_get(key=stored.key), "expires_in": 900}


@router.post("/documents/{document_id}/processing-profiles", response_model=ProcessingProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_processing_profile(document_id: UUID, payload: ProcessingProfileRequest, session: AsyncSession = Depends(get_session), owner_id: UUID = Depends(get_current_user_id)):
    version = await session.scalar(
        select(DocumentStyleVersionModel)
        .join(DocumentStyleModel)
        .where(
            DocumentStyleVersionModel.id == payload.style_version_id,
            DocumentStyleVersionModel.status == "published",
            DocumentStyleModel.owner_id == owner_id,
            DocumentStyleModel.status == "active",
        )
    )
    if not version:
        raise HTTPException(status_code=422, detail="A published style version is required")
    if payload.translation_enabled and not payload.target_language:
        raise HTTPException(status_code=422, detail="Target language is required when translation is enabled")
    now = datetime.now(timezone.utc)
    document = await session.scalar(select(DocumentModel).where(DocumentModel.id == document_id, DocumentModel.owner_id == owner_id))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status not in {"uploaded", "processing_failed"}:
        raise HTTPException(status_code=409, detail="Only an uploaded or failed document can be started again")
    profile = ProcessingProfileModel(id=uuid4(), document_id=document_id, style_version_id=payload.style_version_id, source_language=payload.source_language, target_language=payload.target_language, translation_enabled=payload.translation_enabled, glossary_version_id=payload.glossary_version_id, status="created", created_at=now)
    document.style_version_id = version.id
    document.style_settings = version.settings or {}
    job = Job(document_id=document_id, kind="initial_processing")
    document.status = "queued"
    document.processing_job_id = job.id
    session.add(profile)
    await session.commit()
    await SqlAlchemyJobRepository(session).add(job)
    await CeleryDocumentJobQueue().enqueue_initial_processing(document_id, job.id)
    return ProcessingProfileResponse.model_validate(profile, from_attributes=True)
