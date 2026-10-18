from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StyleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    settings: dict = Field(default_factory=dict)


class StyleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    prompt: str | None = Field(default=None, min_length=1)


class StyleVersionResponse(BaseModel):
    id: UUID
    version: int
    status: str
    manifest_sha256: str
    settings: dict
    validation_report: dict | None
    created_at: datetime
    published_at: datetime | None


class StyleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    current_version: StyleVersionResponse | None
    versions_count: int
    created_at: datetime
    updated_at: datetime


class StyleDetailsResponse(StyleResponse):
    versions: list[StyleVersionResponse]


class StyleVersionUpdateRequest(BaseModel):
    settings: dict = Field(default_factory=dict)


class ProcessingProfileRequest(BaseModel):
    style_version_id: UUID
    source_language: str | None = None
    target_language: str | None = None
    translation_enabled: bool = False
    glossary_version_id: str | None = None


class ProcessingProfileResponse(BaseModel):
    id: UUID
    document_id: UUID
    style_version_id: UUID
    source_language: str | None
    target_language: str | None
    translation_enabled: bool
    glossary_version_id: str | None = None
    status: str
    created_at: datetime
