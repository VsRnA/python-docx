from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
from uuid import UUID

from document_service.domain.value_objects.document_status import DocumentStatus
from document_service.domain.value_objects.job_status import JobStatus
from document_service.domain.value_objects.profile_status import ProcessingProfileStatus
from document_service.infrastructure.database.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyProcessingProfileRepository,
)
from document_service.infrastructure.database.session import async_session_factory, engine
from document_service.infrastructure.queue.tasks import _process, _process_merge

logger = logging.getLogger(__name__)


async def _persist_unhandled_failure(job_id: UUID, document_id: UUID, error: Exception) -> None:
    """Persist failures that happen before a task's own error handler is entered."""
    async with async_session_factory() as session:
        jobs = SqlAlchemyJobRepository(session)
        job = await jobs.get(job_id)
        if job is None or job.status in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }:
            return

        job.fail(code=type(error).__name__, message=str(error))
        await jobs.update(job)

        documents = SqlAlchemyDocumentRepository(session)
        document = await documents.get(document_id)
        if document is not None and document.status in {
            DocumentStatus.QUEUED,
            DocumentStatus.PROCESSING,
        }:
            document.mark_failed()
            await documents.update(document)

        profile = await SqlAlchemyProcessingProfileRepository(session).get_latest(document_id)
        if profile is not None and profile.status in {
            ProcessingProfileStatus.CREATED,
            ProcessingProfileStatus.PROCESSING,
            ProcessingProfileStatus.TRANSLATING,
        }:
            profile.fail()
            await SqlAlchemyProcessingProfileRepository(session).update(profile)

        await session.commit()


async def run() -> None:
    owner = f"{socket.gethostname()}:{os.getpid()}"
    logger.info("Worker started owner=%s", owner)
    try:
        while True:
            async with async_session_factory() as session:
                jobs = SqlAlchemyJobRepository(session)
                job = await jobs.claim_next(owner)
                await session.commit()
            if job is None:
                await asyncio.sleep(1.0)
                continue

            logger.info(
                "Claimed job id=%s document_id=%s kind=%s lease_until=%s",
                job.id,
                job.document_id,
                job.kind,
                job.lease_until,
            )

            async def heartbeat() -> None:
                while True:
                    await asyncio.sleep(60)
                    async with async_session_factory() as heartbeat_session:
                        renewed = await SqlAlchemyJobRepository(heartbeat_session).renew_lease(job.id, owner)
                    if not renewed:
                        return

            heartbeat_task = asyncio.create_task(heartbeat())
            try:
                if job.kind == "merge_processing":
                    await _process_merge(UUID(str(job.document_id)), UUID(str(job.id)))
                else:
                    await _process(UUID(str(job.document_id)), UUID(str(job.id)))
            except Exception as error:
                logger.exception("Job failed id=%s document_id=%s", job.id, job.document_id)
                try:
                    await _persist_unhandled_failure(job.id, job.document_id, error)
                except Exception:
                    logger.exception("Could not persist worker-level failure id=%s", job.id)
                continue
            finally:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())
