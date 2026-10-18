import asyncio
import logging
from hashlib import sha256

import boto3
from botocore.client import Config

from document_service.application.ports.object_storage import StoredObject
from document_service.infrastructure.config.settings import Settings

logger = logging.getLogger(__name__)


class TimewebS3Storage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._download_timeout_seconds = settings.s3_download_timeout_seconds
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(
                signature_version="s3v4",
                connect_timeout=settings.s3_connect_timeout_seconds,
                read_timeout=settings.s3_read_timeout_seconds,
                retries={"max_attempts": settings.s3_max_attempts, "mode": "standard"},
            ),
        )

    async def put(self, *, key: str, content: bytes, content_type: str) -> StoredObject:
        if not self._bucket:
            raise RuntimeError("S3_BUCKET is not configured")
        digest = sha256(content).hexdigest()
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256=digest,
            content_type=content_type,
        )

    async def get(self, *, key: str) -> bytes:
        logger.info("S3 get started key=%s", key)
        async def download() -> bytes:
            response = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
            return await asyncio.to_thread(response["Body"].read)

        content = await asyncio.wait_for(download(), timeout=self._download_timeout_seconds)
        logger.info("S3 get completed key=%s bytes=%s", key, len(content))
        return content

    async def delete(self, *, key: str) -> None:
        if not self._bucket:
            raise RuntimeError("S3_BUCKET is not configured")
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def presign_get(self, *, key: str, expires_seconds: int = 900) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )
