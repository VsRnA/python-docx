from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.domain.entities.asset import Asset
from document_service.domain.entities.document import Document
from document_service.domain.entities.document_version import DocumentVersion
from document_service.domain.entities.job import Job
from document_service.domain.entities.publication import Publication
from document_service.domain.entities.ai_message import AiMessage
from document_service.domain.value_objects.document_status import DocumentStatus
from document_service.infrastructure.database.models import (
    AssetModel,
    DocumentModel,
    DocumentVersionModel,
    JobModel,
    PublicationModel,
    AiMessageModel,
)


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> None:
        self._session.add(self._to_model(document))
        await self._session.commit()

    async def get(self, document_id):
        model = await self._session.get(DocumentModel, document_id)
        return self._to_entity(model) if model else None

    async def list(self, *, owner_id, limit: int, offset: int) -> list[Document]:
        result = await self._session.execute(
            select(DocumentModel)
            .where(
                DocumentModel.owner_id == owner_id,
                DocumentModel.status != DocumentStatus.DELETED.value,
            )
            .order_by(DocumentModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
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
        model.updated_at = document.updated_at
        await self._session.commit()

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
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


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
        await self._session.commit()

    async def get_current(self, document_id):
        result = await self._session.execute(
            select(DocumentVersionModel)
            .where(DocumentVersionModel.document_id == document_id)
            .order_by(DocumentVersionModel.revision.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_revision(self, document_id, revision):
        result = await self._session.execute(
            select(DocumentVersionModel).where(
                DocumentVersionModel.document_id == document_id,
                DocumentVersionModel.revision == revision,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_document(self, document_id):
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
        await self._session.commit()

    async def list_by_document(self, document_id):
        result = await self._session.execute(
            select(AssetModel).where(AssetModel.document_id == document_id)
        )
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

    async def get(self, asset_id):
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


class SqlAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: Job) -> None:
        self._session.add(self._to_model(job))
        await self._session.commit()

    async def get(self, job_id):
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
        await self._session.commit()

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
        )

    @staticmethod
    def _to_entity(model: JobModel) -> Job:
        return Job(
            id=model.id,
            document_id=model.document_id,
            kind=model.kind,
            status=model.status,
            progress=model.progress,
            stage=model.stage,
            error_code=model.error_code,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
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
        await self._session.commit()

    async def list_by_document(self, document_id):
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
            )
            for model in result.scalars()
        ]


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
        await self._session.commit()

    async def list_by_document(self, document_id, *, limit: int = 100):
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
