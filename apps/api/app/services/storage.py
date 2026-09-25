"""
S3/MinIO storage service — LegalLens
Implements: architecture.md §4 (S3-compatible object storage).
Wraps boto3 async calls. In local dev, points at MinIO via S3_ENDPOINT_URL.
In production, S3_ENDPOINT_URL is omitted and boto3 uses AWS endpoints directly.
"""

from __future__ import annotations

import io
from functools import lru_cache

import boto3
import structlog
from botocore.exceptions import ClientError

from app.core.config import settings

log = structlog.get_logger(__name__)


class StorageService:
    """Storage service wrapper for dependency injection and health checks."""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            self._client = _s3_client()
        return self._client
    
    async def upload(self, key: str, data: io.BytesIO, content_type: str) -> None:
        """Upload bytes to S3."""
        return await upload_to_s3(key, data, content_type)
    
    async def delete(self, key: str) -> None:
        """Delete object from S3."""
        return await delete_from_s3(key)
    
    async def generate_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate presigned URL."""
        return await generate_presigned_url(key, expires_in)
    
    async def health_check(self) -> bool:
        """Check storage connectivity."""
        try:
            self.client.list_objects_v2(Bucket=settings.S3_BUCKET, MaxKeys=1)
            return True
        except ClientError as e:
            log.error("s3.health_check_failed", error=str(e))
            raise


# Singleton instance
storage_service = StorageService()


@lru_cache(maxsize=1)
def _s3_client():
    """Singleton S3 client. Cached for connection reuse."""
    kwargs: dict = {
        "region_name": "us-east-1",
        "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


async def upload_to_s3(
    key: str,
    data: io.BytesIO,
    content_type: str,
) -> None:
    """
    Upload bytes to the configured S3 bucket.
    boto3 is synchronous — in production use aioboto3 or run_in_executor.
    Phase 1 uses synchronous upload (file sizes ≤ 20 MB, acceptable for MVP).
    Phase 6 hardening: switch to aioboto3 for non-blocking upload.
    """
    client = _s3_client()
    try:
        client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data.read(),
            ContentType=content_type,
            ServerSideEncryption="AES256",  # SSE-S3; switch to SSE-KMS in prod (Phase 8)
        )
        log.info("s3.uploaded", key=key, content_type=content_type)
    except ClientError as exc:
        log.error("s3.upload_failed", key=key, error=str(exc))
        raise


async def delete_from_s3(key: str) -> None:
    """Delete an object. Called by the document delete endpoint."""
    client = _s3_client()
    try:
        client.delete_object(Bucket=settings.S3_BUCKET, Key=key)
        log.info("s3.deleted", key=key)
    except ClientError as exc:
        log.error("s3.delete_failed", key=key, error=str(exc))
        raise


async def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """
    Generate a time-limited signed download URL.
    Used by the export endpoint (architecture.md §3 step 9).
    """
    client = _s3_client()
    try:
        url: str = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
        log.info("s3.presigned_url_generated", key=key, expires_in=expires_in)
        return url
    except ClientError as e:
        log.error("s3.presigned_url_error", key=key, error=str(e))
        raise


async def health_check() -> bool:
    """
    Health check for storage connectivity.
    Attempts to list bucket (limit 1) to verify access.
    Used by readiness probe (deprecated - use storage_service.health_check()).
    """
    return await storage_service.health_check()

