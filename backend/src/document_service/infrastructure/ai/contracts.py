from typing import Literal

from pydantic import BaseModel, Field


class AstraAssetPayload(BaseModel):
    asset_id: str
    filename: str
    mime_type: Literal["image/png", "image/jpeg", "image/webp", "image/svg+xml"]
    encoding: Literal["base64"] = "base64"
    data: str
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    alt: str = ""


class AstraDocumentPayload(BaseModel):
    document_id: str
    revision: int = 1
    theme_id: str
    theme_version: str
    language: str
    html: str
    assets: list[AstraAssetPayload] = Field(default_factory=list)


class AstraFullDocumentResponse(BaseModel):
    contract_version: Literal["1.0"]
    response_type: Literal["full_document"]
    document: AstraDocumentPayload
    warnings: list[str] = Field(default_factory=list)


class AstraChangeOperation(BaseModel):
    operation: Literal["replace_block", "delete_block", "insert_after"]
    block_id: str
    expected_hash: str
    html: str | None = None


class AstraChangeSetPayload(BaseModel):
    base_revision: int
    summary: str
    operations: list[AstraChangeOperation]
    assets: list[AstraAssetPayload] = Field(default_factory=list)


class AstraChangeSetResponse(BaseModel):
    contract_version: Literal["1.0"]
    response_type: Literal["change_set"]
    change_set: AstraChangeSetPayload
    warnings: list[str] = Field(default_factory=list)
