from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.application.ports.document_state_repository import (
    DocumentCommentData,
    DocumentSnapshotData,
)
from document_service.application.ports.style_repository import StyleData, StyleRepository, StyleVersionData
from document_service.domain.entities.ai_message import AiMessage
from document_service.domain.entities.ai_edit_proposal import AiEditProposal
from document_service.domain.entities.asset import Asset
from document_service.domain.entities.document import Document
from document_service.domain.entities.document_source_file import DocumentSourceFile
from document_service.domain.entities.document_version import DocumentVersion
from document_service.domain.entities.job import Job
from document_service.domain.entities.processing_profile import ProcessingProfile
from document_service.domain.entities.publication import Publication
from document_service.domain.value_objects.document_status import DocumentStatus
from document_service.domain.value_objects.job_status import JobStatus
from document_service.domain.value_objects.profile_status import ProcessingProfileStatus
from document_service.infrastructure.database.models import (
    AiMessageModel,
    AiEditProposalModel,
    AiResponseModel,
    AssetModel,
    DocumentCommentModel,
    DocumentModel,
    DocumentSnapshotModel,
    DocumentSourceFileModel,
    DocumentStyleModel,
    DocumentStyleVersionModel,
    DocumentVersionModel,
    JobModel,
    ProcessingProfileModel,
    PublicationModel,
)


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> None:
        self._session.add(self._to_model(document))
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def get(self, document_id: UUID) -> Document | None:
        model = await self._session.get(DocumentModel, document_id)
        return self._to_entity(model) if model else None

    async def get_owned(self, document_id: UUID, *, owner_id: UUID) -> Document | None:
        model = await self._session.scalar(
            select(DocumentModel).where(DocumentModel.id == document_id, DocumentModel.owner_id == owner_id)
        )
        return self._to_entity(model) if model else None

    async def list(
        self,
        *,
        owner_id,
        limit: int,
        offset: int,
        search: str | None = None,
        status: str | None = None,
        sort: str = "updated",
    ) -> list[Document]:
        query = select(DocumentModel).where(
            DocumentModel.owner_id == owner_id, DocumentModel.status != DocumentStatus.DELETED.value
        )
        if search:
            query = query.where(
                DocumentModel.title.ilike(f"%{search}%") | DocumentModel.source_filename.ilike(f"%{search}%")
            )
        if status:
            query = query.where(DocumentModel.status == status)
        order_column = (
            DocumentModel.title
            if sort == "title"
            else DocumentModel.created_at
            if sort == "created"
            else DocumentModel.updated_at
        )
        result = await self._session.execute(
            query.order_by(order_column.asc() if sort == "title" else order_column.desc()).limit(limit).offset(offset)
        )
        return [self._to_entity(model) for model in result.scalars()]

    async def update(self, document: Document) -> None:
        model = await self._session.get(DocumentModel, document.id)
        if model is None:
            raise LookupError(f"Document {document.id} does not exist")
        model.title = document.title
        model.status = document.status.value
        model.current_revision = document.current_revision
        model.source_object_key = document.source_object_key
        model.processing_job_id = document.processing_job_id
        model.style_settings = document.style_settings
        model.pipeline_metadata = document.pipeline_metadata
        model.source_sha256 = document.source_sha256
        model.style_reference_sha256 = document.style_reference_sha256
        model.updated_at = document.updated_at
        await self._session.flush()

    async def save_version_atomically(self, document: Document, version: DocumentVersion) -> bool:
        result = await self._session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == document.id,
                DocumentModel.current_revision == version.revision - 1,
            )
            .values(
                current_revision=version.revision,
                updated_at=document.updated_at,
            )
        )
        if result.rowcount != 1:
            await self._session.rollback()
            return False
        self._session.add(
            DocumentVersionModel(
                id=version.id,
                document_id=version.document_id,
                revision=version.revision,
                html=version.html,
                astra_html=version.astra_html,
                theme_id=version.theme_id,
                theme_version=version.theme_version,
                created_by=version.created_by,
                reason=version.reason,
                created_at=version.created_at,
            )
        )
        await self._session.commit()
        return True

    @staticmethod
    def _to_model(document: Document) -> DocumentModel:
        return DocumentModel(
            id=document.id,
            title=document.title,
            source_filename=document.source_filename,
            source_size_bytes=document.source_size_bytes,
            source_object_key=document.source_object_key,
            owner_id=document.owner_id,
            status=document.status.value,
            current_revision=document.current_revision,
            processing_job_id=document.processing_job_id,
            style_version_id=document.style_version_id,
            style_settings=document.style_settings,
            pipeline_metadata=document.pipeline_metadata,
            source_sha256=document.source_sha256,
            style_reference_sha256=document.style_reference_sha256,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _to_entity(model: DocumentModel) -> Document:
        return Document(
            id=model.id,
            title=model.title,
            source_filename=model.source_filename,
            source_size_bytes=model.source_size_bytes,
            source_object_key=model.source_object_key,
            owner_id=model.owner_id,
            status=DocumentStatus(model.status),
            current_revision=model.current_revision,
            processing_job_id=model.processing_job_id,
            style_version_id=model.style_version_id,
            style_settings=model.style_settings or {},
            pipeline_metadata=model.pipeline_metadata or {},
            source_sha256=model.source_sha256,
            style_reference_sha256=model.style_reference_sha256,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SqlAlchemyAiEditProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, proposal: AiEditProposal) -> None:
        self._session.add(
            AiEditProposalModel(
                id=proposal.id,
                document_id=proposal.document_id,
                owner_id=proposal.owner_id,
                base_revision=proposal.base_revision,
                summary=proposal.summary,
                before_html=proposal.before_html,
                after_html=proposal.after_html,
                operations=proposal.operations,
                status=proposal.status,
                accepted_revision=proposal.accepted_revision,
                created_at=proposal.created_at,
            )
        )
        await self._session.flush()

    async def get_owned(self, proposal_id: UUID, owner_id: UUID) -> AiEditProposal | None:
        model = await self._session.scalar(
            select(AiEditProposalModel).where(
                AiEditProposalModel.id == proposal_id,
                AiEditProposalModel.owner_id == owner_id,
            )
        )
        if model is None:
            return None
        return AiEditProposal(
            id=model.id,
            document_id=model.document_id,
            owner_id=model.owner_id,
            base_revision=model.base_revision,
            summary=model.summary,
            before_html=model.before_html,
            after_html=model.after_html,
            operations=model.operations or [],
            status=model.status,
            accepted_revision=model.accepted_revision,
            created_at=model.created_at,
        )

    async def mark_accepted(self, proposal_id: UUID, revision: int) -> None:
        model = await self._session.get(AiEditProposalModel, proposal_id)
        if model is None:
            raise LookupError(f"AI edit proposal {proposal_id} does not exist")
        model.status = "accepted"
        model.accepted_revision = revision
        await self._session.flush()


class SqlAlchemyDocumentVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, version: DocumentVersion) -> None:
        self._session.add(
            DocumentVersionModel(
                id=version.id,
                document_id=version.document_id,
                revision=version.revision,
                html=version.html,
                astra_html=version.astra_html,
                theme_id=version.theme_id,
                theme_version=version.theme_version,
                created_by=version.created_by,
                reason=version.reason,
                created_at=version.created_at,
            )
        )
        await self._session.flush()

    async def update(self, version: DocumentVersion) -> None:
        model = await self._session.get(DocumentVersionModel, version.id)
        if model is None:
            raise LookupError(f"Document version {version.id} does not exist")
        model.html = version.html
        model.astra_html = version.astra_html
        await self._session.flush()

    async def get_current(self, document_id: UUID) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersionModel)
            .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
            .where(
                DocumentVersionModel.document_id == document_id,
                DocumentVersionModel.revision == DocumentModel.current_revision,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_revision(self, document_id: UUID, revision: int) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersionModel).where(
                DocumentVersionModel.document_id == document_id,
                DocumentVersionModel.revision == revision,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_document(self, document_id: UUID) -> list[DocumentVersion]:
        result = await self._session.execute(
            select(DocumentVersionModel)
            .where(DocumentVersionModel.document_id == document_id)
            .order_by(DocumentVersionModel.revision.desc())
        )
        return [self._to_entity(model) for model in result.scalars()]

    @staticmethod
    def _to_entity(model: DocumentVersionModel) -> DocumentVersion:
        return DocumentVersion(
            id=model.id,
            document_id=model.document_id,
            revision=model.revision,
            html=model.html,
            astra_html=model.astra_html,
            theme_id=model.theme_id,
            theme_version=model.theme_version,
            created_by=model.created_by,
            reason=model.reason,
            created_at=model.created_at,
        )


class SqlAlchemyAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, assets: list[Asset]) -> None:
        self._session.add_all(
            [
                AssetModel(
                    id=asset.id,
                    document_id=asset.document_id,
                    storage_key=asset.storage_key,
                    mime_type=asset.mime_type,
                    size_bytes=asset.size_bytes,
                    sha256=asset.sha256,
                    filename=asset.filename,
                    width=asset.width,
                    height=asset.height,
                    alt=asset.alt,
                    created_at=asset.created_at,
                )
                for asset in assets
            ]
        )
        await self._session.flush()

    async def list_by_document(self, document_id: UUID) -> list[Asset]:
        result = await self._session.execute(select(AssetModel).where(AssetModel.document_id == document_id))
        return [
            Asset(
                id=model.id,
                document_id=model.document_id,
                storage_key=model.storage_key,
                mime_type=model.mime_type,
                size_bytes=model.size_bytes,
                sha256=model.sha256,
                filename=model.filename,
                width=model.width,
                height=model.height,
                alt=model.alt,
                created_at=model.created_at,
            )
            for model in result.scalars()
        ]

    @staticmethod
    def _to_entity(model: DocumentVersionModel) -> DocumentVersion:
        return DocumentVersion(
            id=model.id,
            document_id=model.document_id,
            revision=model.revision,
            html=model.html,
            astra_html=model.astra_html,
            theme_id=model.theme_id,
            theme_version=model.theme_version,
            created_by=model.created_by,
            reason=model.reason,
            created_at=model.created_at,
        )

    async def get(self, asset_id: UUID) -> Asset | None:
        model = await self._session.get(AssetModel, asset_id)
        if model is None:
            return None
        return Asset(
            id=model.id,
            document_id=model.document_id,
            storage_key=model.storage_key,
            mime_type=model.mime_type,
            size_bytes=model.size_bytes,
            sha256=model.sha256,
            filename=model.filename,
            width=model.width,
            height=model.height,
            alt=model.alt,
            created_at=model.created_at,
        )


class SqlAlchemyDocumentSourceFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, source_files: list[DocumentSourceFile]) -> None:
        self._session.add_all(
            [
                DocumentSourceFileModel(
                    id=source.id,
                    document_id=source.document_id,
                    source_document_id=source.source_document_id,
                    filename=source.filename,
                    object_key=source.object_key,
                    size_bytes=source.size_bytes,
                    sha256=source.sha256,
                    position=source.position,
                    role=source.role,
                    created_at=source.created_at,
                )
                for source in source_files
            ]
        )
        await self._session.flush()

    async def list_by_document(self, document_id: UUID) -> list[DocumentSourceFile]:
        result = await self._session.execute(
            select(DocumentSourceFileModel)
            .where(DocumentSourceFileModel.document_id == document_id)
            .order_by(DocumentSourceFileModel.position.asc())
        )
        return [
            DocumentSourceFile(
                id=model.id,
                document_id=model.document_id,
                source_document_id=model.source_document_id,
                filename=model.filename,
                object_key=model.object_key,
                size_bytes=model.size_bytes,
                sha256=model.sha256,
                position=model.position,
                role=model.role,
                created_at=model.created_at,
            )
            for model in result.scalars()
        ]


class SqlAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: Job) -> None:
        self._session.add(self._to_model(job))
        await self._session.flush()

    async def get(self, job_id: UUID) -> Job | None:
        model = await self._session.get(JobModel, job_id)
        return self._to_entity(model) if model else None

    async def update(self, job: Job) -> None:
        model = await self._session.get(JobModel, job.id)
        if model is None:
            raise LookupError(f"Job {job.id} does not exist")
        model.status = job.status
        model.progress = job.progress
        model.stage = job.stage
        model.error_code = job.error_code
        model.error_message = job.error_message
        model.started_at = job.started_at
        model.finished_at = job.finished_at
        model.lease_owner = job.lease_owner
        model.lease_until = job.lease_until
        await self._session.flush()

    async def claim_next(self, owner: str, lease_seconds: int = 900) -> Job | None:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(JobModel)
            .where(
                or_(
                    JobModel.status == JobStatus.QUEUED.value,
                    and_(
                        JobModel.status == JobStatus.RUNNING.value,
                        JobModel.lease_until.is_not(None),
                        JobModel.lease_until < now,
                    ),
                ),
            )
            .order_by(JobModel.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        if model.status == JobStatus.RUNNING.value:
            model.status = JobStatus.QUEUED.value
            model.stage = "queued"
            model.progress = 0
            model.started_at = None
            model.finished_at = None
            model.error_code = None
            model.error_message = None
        model.lease_owner = owner
        model.lease_until = now + timedelta(seconds=lease_seconds)
        await self._session.flush()
        return self._to_entity(model)

    async def renew_lease(self, job_id: UUID, owner: str, lease_seconds: int = 900) -> bool:
        result = await self._session.execute(
            update(JobModel)
            .where(JobModel.id == job_id, JobModel.lease_owner == owner, JobModel.status.in_(["queued", "running"]))
            .values(lease_until=datetime.now(UTC) + timedelta(seconds=lease_seconds))
        )
        await self._session.commit()
        return result.rowcount == 1

    @staticmethod
    def _to_model(job: Job) -> JobModel:
        return JobModel(
            id=job.id,
            document_id=job.document_id,
            kind=job.kind,
            status=job.status,
            progress=job.progress,
            stage=job.stage,
            error_code=job.error_code,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            lease_owner=job.lease_owner,
            lease_until=job.lease_until,
        )

    @staticmethod
    def _to_entity(model: JobModel) -> Job:
        return Job(
            id=model.id,
            document_id=model.document_id,
            kind=model.kind,
            status=JobStatus(model.status),
            progress=model.progress,
            stage=model.stage,
            error_code=model.error_code,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
            lease_owner=model.lease_owner,
            lease_until=model.lease_until,
        )


class SqlAlchemyDocumentStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_snapshot(self, document_id: UUID, revision: int) -> DocumentSnapshotData | None:
        model = await self._session.scalar(
            select(DocumentSnapshotModel).where(
                DocumentSnapshotModel.document_id == document_id,
                DocumentSnapshotModel.revision == revision,
            )
        )
        if model is None:
            return None
        return DocumentSnapshotData(
            revision=model.revision,
            document_tree=model.document_tree,
            pagination_snapshot=model.pagination_snapshot,
        )

    async def save_snapshot(
        self,
        document_id: UUID,
        snapshot: DocumentSnapshotData,
        *,
        snapshot_id: UUID,
        created_at: datetime,
    ) -> None:
        self._session.add(
            DocumentSnapshotModel(
                id=snapshot_id,
                document_id=document_id,
                revision=snapshot.revision,
                document_tree=snapshot.document_tree,
                pagination_snapshot=snapshot.pagination_snapshot,
                created_at=created_at,
            )
        )
        await self._session.flush()

    async def list_comments(self, document_id: UUID) -> list[DocumentCommentData]:
        result = await self._session.execute(
            select(DocumentCommentModel)
            .where(DocumentCommentModel.document_id == document_id)
            .order_by(DocumentCommentModel.created_at)
        )
        return [self._comment_data(model) for model in result.scalars()]

    async def add_comment(self, document_id: UUID, *, block_id: str | None, text: str) -> DocumentCommentData:
        model = DocumentCommentModel(
            id=uuid4(),
            document_id=document_id,
            block_id=block_id,
            text=text,
            status="open",
            created_at=datetime.now(UTC),
        )
        self._session.add(model)
        await self._session.flush()
        return self._comment_data(model)

    async def update_comment(
        self,
        comment_id: UUID,
        *,
        owner_id: UUID,
        text: str | None,
        status: str | None,
    ) -> DocumentCommentData | None:
        model = await self._session.scalar(
            select(DocumentCommentModel)
            .join(DocumentModel, DocumentModel.id == DocumentCommentModel.document_id)
            .where(
                DocumentCommentModel.id == comment_id,
                DocumentModel.owner_id == owner_id,
            )
        )
        if model is None:
            return None
        if text is not None:
            model.text = text
        if status is not None:
            model.status = status
        await self._session.flush()
        return self._comment_data(model)

    @staticmethod
    def _comment_data(model):
        return DocumentCommentData(
            id=model.id,
            document_id=model.document_id,
            block_id=model.block_id,
            text=model.text,
            status=model.status,
            created_at=model.created_at,
        )


class SqlAlchemyPublicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, publication: Publication) -> None:
        self._session.add(
            PublicationModel(
                id=publication.id,
                document_id=publication.document_id,
                revision=publication.revision,
                object_key=publication.object_key,
                created_by=publication.created_by,
                created_at=publication.created_at,
            )
        )
        await self._session.flush()

    async def list_by_document(self, document_id: UUID) -> list[Publication]:
        result = await self._session.execute(
            select(PublicationModel)
            .where(PublicationModel.document_id == document_id)
            .order_by(PublicationModel.created_at.desc())
        )
        return [
            Publication(
                id=model.id,
                document_id=model.document_id,
                revision=model.revision,
                object_key=model.object_key,
                created_by=model.created_by,
                created_at=model.created_at,
                revoked_at=model.revoked_at,
            )
            for model in result.scalars()
        ]

    async def get_for_document(self, publication_id: UUID, document_id: UUID) -> Publication | None:
        model = await self._session.scalar(
            select(PublicationModel).where(
                PublicationModel.id == publication_id,
                PublicationModel.document_id == document_id,
            )
        )
        if model is None:
            return None
        return Publication(
            id=model.id,
            document_id=model.document_id,
            revision=model.revision,
            object_key=model.object_key,
            created_by=model.created_by,
            created_at=model.created_at,
            revoked_at=model.revoked_at,
        )

    async def update(self, publication: Publication) -> None:
        model = await self._session.get(PublicationModel, publication.id)
        if model is None:
            raise LookupError(f"Publication {publication.id} does not exist")
        model.revoked_at = publication.revoked_at
        await self._session.flush()


class SqlAlchemyStyleRepository(StyleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, owner_id: UUID) -> list[StyleData]:
        styles = list(
            (
                await self._session.execute(
                    select(DocumentStyleModel)
                    .where(DocumentStyleModel.owner_id == owner_id)
                    .order_by(DocumentStyleModel.updated_at.desc())
                )
            ).scalars()
        )
        return await self._with_details(styles)

    async def get(self, style_id: UUID, *, owner_id: UUID) -> StyleData | None:
        style = await self._session.scalar(
            select(DocumentStyleModel).where(
                DocumentStyleModel.id == style_id,
                DocumentStyleModel.owner_id == owner_id,
            )
        )
        if style is None:
            return None
        detailed = await self._with_details([style])
        return detailed[0]

    async def get_version(self, version_id: UUID, *, owner_id: UUID) -> StyleVersionData | None:
        version = await self._session.scalar(
            select(DocumentStyleVersionModel)
            .join(DocumentStyleModel)
            .where(
                DocumentStyleVersionModel.id == version_id,
                DocumentStyleModel.owner_id == owner_id,
            )
        )
        return self._version_data(version) if version else None

    async def get_published_version(self, version_id: UUID, *, owner_id: UUID) -> StyleVersionData | None:
        version = await self._session.scalar(
            select(DocumentStyleVersionModel)
            .join(DocumentStyleModel)
            .where(
                DocumentStyleVersionModel.id == version_id,
                DocumentStyleVersionModel.status == "published",
                DocumentStyleModel.owner_id == owner_id,
                DocumentStyleModel.status == "active",
            )
        )
        return self._version_data(version) if version else None

    async def add(self, style: StyleData, version: StyleVersionData) -> None:
        self._session.add(
            DocumentStyleModel(
                id=style.id,
                name=style.name,
                description=style.description,
                owner_id=style.owner_id,
                status=style.status,
                created_at=style.created_at,
                updated_at=style.updated_at,
            )
        )
        await self.add_version(version)

    async def ensure_default(self, style: StyleData, version: StyleVersionData) -> StyleData:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"document-service:default-style:{style.owner_id}"},
        )
        existing = await self._session.scalar(
            select(DocumentStyleModel)
            .join(DocumentStyleVersionModel)
            .where(
                DocumentStyleModel.owner_id == style.owner_id,
                DocumentStyleModel.name == style.name,
                DocumentStyleVersionModel.status == "published",
            )
            .order_by(DocumentStyleModel.created_at.asc())
        )
        if existing is not None:
            result = await self._with_details([existing])
            return result[0]
        await self.add(style, version)
        await self.commit()
        return (await self._with_details([await self._session.get(DocumentStyleModel, style.id)]))[0]

    async def add_version(self, version: StyleVersionData) -> None:
        self._session.add(
            DocumentStyleVersionModel(
                id=version.id,
                style_id=version.style_id,
                version=version.version,
                status=version.status,
                manifest=version.manifest,
                manifest_sha256=version.manifest_sha256,
                settings=version.settings,
                prompt=version.settings.get("style_prompt") if isinstance(version.settings.get("style_prompt"), str) else None,
                reference_object_key=(version.settings.get("reference_file") or {}).get("key")
                if isinstance(version.settings.get("reference_file"), dict)
                else None,
                reference_filename=(version.settings.get("reference_file") or {}).get("filename")
                if isinstance(version.settings.get("reference_file"), dict)
                else None,
                reference_sha256=(version.settings.get("reference_file") or {}).get("sha256")
                if isinstance(version.settings.get("reference_file"), dict)
                else None,
                reference_size_bytes=(version.settings.get("reference_file") or {}).get("size_bytes")
                if isinstance(version.settings.get("reference_file"), dict)
                else None,
                validation_report=version.validation_report,
                created_by=version.created_by,
                created_at=version.created_at,
                published_at=version.published_at,
            )
        )
        await self._session.flush()

    async def update_style(self, style: StyleData) -> None:
        model = await self._session.get(DocumentStyleModel, style.id)
        if model is None:
            raise LookupError(f"Style {style.id} does not exist")
        model.name = style.name
        model.description = style.description
        model.status = style.status
        model.updated_at = style.updated_at
        await self._session.flush()

    async def update_version(self, version: StyleVersionData) -> None:
        model = await self._session.get(DocumentStyleVersionModel, version.id)
        if model is None:
            raise LookupError(f"Style version {version.id} does not exist")
        model.manifest = version.manifest
        model.manifest_sha256 = version.manifest_sha256
        model.settings = version.settings
        model.prompt = version.settings.get("style_prompt") if isinstance(version.settings.get("style_prompt"), str) else None
        reference = version.settings.get("reference_file")
        model.reference_object_key = reference.get("key") if isinstance(reference, dict) else None
        model.reference_filename = reference.get("filename") if isinstance(reference, dict) else None
        model.reference_sha256 = reference.get("sha256") if isinstance(reference, dict) else None
        model.reference_size_bytes = reference.get("size_bytes") if isinstance(reference, dict) else None
        model.validation_report = version.validation_report
        model.status = version.status
        model.published_at = version.published_at
        await self._session.flush()

    async def delete(self, style_id: UUID, *, owner_id: UUID) -> bool:
        style = await self._session.scalar(
            select(DocumentStyleModel).where(
                DocumentStyleModel.id == style_id,
                DocumentStyleModel.owner_id == owner_id,
            )
        )
        if style is None:
            return False
        await self._session.delete(style)
        await self._session.flush()
        return True

    async def archive_published_versions(self, style_id: UUID) -> None:
        await self._session.execute(
            update(DocumentStyleVersionModel)
            .where(
                DocumentStyleVersionModel.style_id == style_id,
                DocumentStyleVersionModel.status == "published",
            )
            .values(status="archived")
        )

    async def commit(self) -> None:
        await self._session.commit()

    async def _with_details(self, styles: list[DocumentStyleModel]) -> list[StyleData]:
        if not styles:
            return []
        style_ids = [style.id for style in styles]
        versions = list(
            (
                await self._session.execute(
                    select(DocumentStyleVersionModel)
                    .where(DocumentStyleVersionModel.style_id.in_(style_ids))
                    .order_by(DocumentStyleVersionModel.version.desc())
                )
            ).scalars()
        )
        versions_by_style: dict[UUID, list[StyleVersionData]] = {style_id: [] for style_id in style_ids}
        for version in versions:
            versions_by_style[version.style_id].append(self._version_data(version))
        return [
            StyleData(
                id=style.id,
                name=style.name,
                description=style.description,
                owner_id=style.owner_id,
                status=style.status,
                created_at=style.created_at,
                updated_at=style.updated_at,
                versions=tuple(versions_by_style[style.id]),
            )
            for style in styles
        ]

    @staticmethod
    def _version_data(model: DocumentStyleVersionModel) -> StyleVersionData:
        settings = dict(model.settings or {})
        if model.prompt is not None:
            settings["style_prompt"] = model.prompt
        if model.reference_object_key:
            settings["reference_file"] = {
                "key": model.reference_object_key,
                "filename": model.reference_filename,
                "sha256": model.reference_sha256,
                "size_bytes": model.reference_size_bytes,
            }
        return StyleVersionData(
            id=model.id,
            style_id=model.style_id,
            version=model.version,
            status=model.status,
            manifest=model.manifest or {},
            manifest_sha256=model.manifest_sha256,
            settings=settings,
            validation_report=model.validation_report,
            created_by=model.created_by,
            created_at=model.created_at,
            published_at=model.published_at,
        )


class SqlAlchemyProcessingProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, profile: ProcessingProfile) -> None:
        self._session.add(
            ProcessingProfileModel(
                id=profile.id,
                document_id=profile.document_id,
                style_version_id=profile.style_version_id,
                source_language=profile.source_language,
                target_language=profile.target_language,
                translation_enabled=profile.translation_enabled,
                glossary_version_id=profile.glossary_version_id,
                status=profile.status,
                created_at=profile.created_at,
            )
        )
        await self._session.flush()

    async def get_latest(self, document_id: UUID) -> ProcessingProfile | None:
        model = await self._session.scalar(
            select(ProcessingProfileModel)
            .where(ProcessingProfileModel.document_id == document_id)
            .order_by(ProcessingProfileModel.created_at.desc())
        )
        if model is None:
            return None
        return ProcessingProfile(
            id=model.id,
            document_id=model.document_id,
            style_version_id=model.style_version_id,
            source_language=model.source_language,
            target_language=model.target_language,
            translation_enabled=model.translation_enabled,
            glossary_version_id=model.glossary_version_id,
            status=ProcessingProfileStatus(model.status),
            created_at=model.created_at,
        )

    async def update(self, profile: ProcessingProfile) -> None:
        model = await self._session.get(ProcessingProfileModel, profile.id)
        if model is None:
            raise LookupError(f"Processing profile {profile.id} does not exist")
        model.status = profile.status.value
        await self._session.flush()


class SqlAlchemyAiMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, messages: list[AiMessage]) -> None:
        self._session.add_all(
            [
                AiMessageModel(
                    id=message.id,
                    document_id=message.document_id,
                    role=message.role,
                    content=message.content,
                    revision=message.revision,
                    created_at=message.created_at,
                )
                for message in messages
            ]
        )
        await self._session.flush()

    async def list_by_document(self, document_id: UUID, *, limit: int = 100) -> list[AiMessage]:
        result = await self._session.execute(
            select(AiMessageModel)
            .where(AiMessageModel.document_id == document_id)
            .order_by(AiMessageModel.created_at.desc())
            .limit(limit)
        )
        return [
            AiMessage(
                id=model.id,
                document_id=model.document_id,
                role=model.role,
                content=model.content,
                revision=model.revision,
                created_at=model.created_at,
            )
            for model in reversed(result.scalars().all())
        ]


class SqlAlchemyAiResponseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document_id: UUID, audit) -> None:
        self._session.add(
            AiResponseModel(
                id=uuid4(),
                document_id=document_id,
                response_id=audit.response_id,
                model=audit.model,
                reasoning_effort=audit.reasoning_effort,
                output_text=audit.output_text,
                status=audit.status,
                usage=audit.usage,
                error_message=audit.error_message,
                created_at=audit.created_at,
            )
        )
        await self._session.flush()

    async def latest_invalid_output(self, document_id: UUID) -> str | None:
        result = await self._session.execute(
            select(AiResponseModel.output_text)
            .where(
                AiResponseModel.document_id == document_id,
                AiResponseModel.status == "invalid",
                AiResponseModel.output_text.is_not(None),
            )
            .order_by(AiResponseModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
