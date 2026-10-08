from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from document_service.domain.value_objects.document_status import DocumentStatus


class CreateDocumentResponse(BaseModel):
    document_id: UUID
    job_id: str


class CreateMergedDocumentResponse(BaseModel):
    document_id: UUID
    job_id: str
    source_count: int


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    source_filename: str
    source_size_bytes: int
    status: DocumentStatus
    current_revision: int
    created_at: datetime
    updated_at: datetime


class DocumentDetailsResponse(BaseModel):
    id: UUID
    title: str
    source_filename: str
    source_size_bytes: int
    status: DocumentStatus
    current_revision: int
    processing_job_id: UUID | None = None
    style_version_id: UUID | None = None
    style_settings: dict = Field(default_factory=dict)
    processing_profile: dict | None = None
    html: str | None
    astra_html: str | None
    theme_id: str | None
    theme_version: str | None
    asset_urls: dict[str, str] = Field(default_factory=dict)


class DocumentVersionResponse(BaseModel):
    revision: int
    reason: str
    created_by: UUID | None
    created_at: datetime


class RestoreVersionRequest(BaseModel):
    base_revision: int
    source_revision: int


class TranslateDocumentRequest(BaseModel):
    base_revision: int
    source_language: str
    target_language: str
    glossary_version: str | None = None


class AiEditRequest(BaseModel):
    base_revision: int
    instruction: str
    target_block_ids: list[str] = Field(default_factory=list)


class AiEditResponse(BaseModel):
    revision: int
    summary: str


class AiEditProposalResponse(BaseModel):
    base_revision: int
    summary: str
    before_html: str
    after_html: str
    operations: list[dict]


class AiMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    revision: int
    created_at: datetime


class PublishDocumentResponse(BaseModel):
    id: UUID
    url: str
    revision: int
    expires_in: int | None


class PublicationListItem(BaseModel):
    id: UUID
    revision: int
    url: str
    expires_in: int | None
    created_at: datetime
    revoked_at: datetime | None = None


class SaveDocumentRequest(BaseModel):
    base_revision: int
    html: str


class RenameDocumentRequest(BaseModel):
    title: str


class SaveDocumentResponse(BaseModel):
    revision: int


class ExportPdfResponse(BaseModel):
    url: str
    expires_in: int


class ExportHtmlPreviewResponse(BaseModel):
    url: str
    expires_in: int


class DocumentOperationRequest(BaseModel):
    operation_id: UUID
    operation_type: str
    block_id: str
    payload: dict = Field(default_factory=dict)


class ApplyOperationsRequest(BaseModel):
    base_revision: int
    operations: list[DocumentOperationRequest]


class DocumentSnapshotResponse(BaseModel):
    document_id: UUID
    revision: int
    metadata: dict
    blocks: list[dict] = Field(default_factory=list)
    layout: dict = Field(default_factory=dict)
    comments: list[dict] = Field(default_factory=list)


class DocumentCommentCreateRequest(BaseModel):
    block_id: str | None = None
    text: str = Field(min_length=1, max_length=4000)


class DocumentCommentUpdateRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=4000)
    status: str | None = None
