from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_service.infrastructure.database.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_object_key: Mapped[str | None] = mapped_column(String(1500))
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_job_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentVersionModel(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        Index("uq_document_versions_revision", "document_id", "revision", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    astra_html: Mapped[str | None] = mapped_column(Text)
    theme_id: Mapped[str] = mapped_column(String(255), nullable=False)
    theme_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssetModel(Base):
    __tablename__ = "assets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(1500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    alt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentSourceFileModel(Base):
    __tablename__ = "document_source_files"
    __table_args__ = (
        Index("ix_document_source_files_document_position", "document_id", "position"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    filename: Mapped[str] = mapped_column(String(1000), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str] = mapped_column(String(128), nullable=False, default="queued")
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PublicationModel(Base):
    __tablename__ = "publications"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(1500), nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AiMessageModel(Base):
    __tablename__ = "ai_messages"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
