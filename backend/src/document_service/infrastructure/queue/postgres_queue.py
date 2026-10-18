from uuid import UUID


class PostgresDocumentJobQueue:
    async def enqueue_initial_processing(self, document_id: UUID, job_id: UUID) -> str:
        return str(job_id)

    async def enqueue_merge_processing(self, document_id: UUID, job_id: UUID) -> str:
        return str(job_id)

    async def revoke(self, job_id: UUID, *, terminate: bool) -> None:
        return None
