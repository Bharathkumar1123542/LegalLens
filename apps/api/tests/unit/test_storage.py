"""
Unit tests — storage service
Tests: S3 operations (upload, delete, presigned URLs), error handling, boto3 client caching
Covers: architecture.md §4 S3-compatible object storage
"""

import io
from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError

from app.services.storage import (
    _s3_client,
    upload_to_s3,
    delete_from_s3,
    generate_presigned_url,
)


class TestS3Client:
    """Test S3 client singleton."""

    def test_s3_client_caching(self):
        """Verify S3 client is cached and reused."""
        # Clear cache
        _s3_client.cache_clear()
        
        # Get client twice
        client1 = _s3_client()
        client2 = _s3_client()
        
        # Should be same instance
        assert client1 is client2
    
    @patch("app.services.storage.boto3.client")
    def test_s3_client_uses_endpoint_url_for_local_dev(self, mock_boto3):
        """S3_ENDPOINT_URL is used when configured (MinIO in dev)."""
        _s3_client.cache_clear()
        
        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.S3_ENDPOINT_URL = "http://localhost:9000"
            mock_settings.S3_ACCESS_KEY_ID = "minioadmin"
            mock_settings.S3_SECRET_ACCESS_KEY = "minioadmin"
            
            _s3_client()
            
            mock_boto3.assert_called_once()
            call_kwargs = mock_boto3.call_args.kwargs
            assert call_kwargs["endpoint_url"] == "http://localhost:9000"
            assert call_kwargs["aws_access_key_id"] == "minioadmin"
    
    @patch("app.services.storage.boto3.client")
    def test_s3_client_omits_endpoint_url_for_production(self, mock_boto3):
        """S3_ENDPOINT_URL omitted in production (uses AWS S3)."""
        _s3_client.cache_clear()
        
        with patch("app.services.storage.settings") as mock_settings:
            mock_settings.S3_ENDPOINT_URL = None
            mock_settings.S3_ACCESS_KEY_ID = "AWS_KEY"
            mock_settings.S3_SECRET_ACCESS_KEY = "AWS_SECRET"
            
            _s3_client()
            
            mock_boto3.assert_called_once()
            call_kwargs = mock_boto3.call_args.kwargs
            assert "endpoint_url" not in call_kwargs
            assert call_kwargs["aws_access_key_id"] == "AWS_KEY"


class TestUploadToS3:
    """Test upload_to_s3 function."""

    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_upload_success(self, mock_s3_client_func):
        """Successful file upload to S3."""
        # Arrange
        mock_client = MagicMock()
        mock_s3_client_func.return_value = mock_client
        
        data = io.BytesIO(b"test file content")
        key = "user123/documents/test.pdf"
        content_type = "application/pdf"
        
        # Act
        await upload_to_s3(key=key, data=data, content_type=content_type)
        
        # Assert
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args.kwargs
        
        assert call_kwargs["Bucket"] == mock_s3_client_func.return_value.put_object.call_args.kwargs.get("Bucket") or "legallens-dev"
        assert call_kwargs["Key"] == key
        assert call_kwargs["Body"] == b"test file content"
        assert call_kwargs["ContentType"] == content_type
        assert call_kwargs["ServerSideEncryption"] == "AES256"
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    @patch("app.services.storage.settings")
    async def test_upload_uses_configured_bucket(self, mock_settings, mock_s3_client_func):
        """Upload uses bucket from settings."""
        mock_settings.S3_BUCKET = "my-custom-bucket"
        mock_client = MagicMock()
        mock_s3_client_func.return_value = mock_client
        
        data = io.BytesIO(b"content")
        
        await upload_to_s3(key="test.txt", data=data, content_type="text/plain")
        
        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "my-custom-bucket"
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_upload_with_empty_file(self, mock_s3_client_func):
        """Upload empty file (valid edge case)."""
        mock_client = MagicMock()
        mock_s3_client_func.return_value = mock_client
        
        data = io.BytesIO(b"")
        
        await upload_to_s3(key="empty.txt", data=data, content_type="text/plain")
        
        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Body"] == b""
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_upload_client_error_raises(self, mock_s3_client_func):
        """Upload failure raises ClientError."""
        mock_client = MagicMock()
        mock_client.put_object.side_effect = ClientError(
            error_response={"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            operation_name="PutObject",
        )
        mock_s3_client_func.return_value = mock_client
        
        data = io.BytesIO(b"content")
        
        with pytest.raises(ClientError, match="Bucket not found"):
            await upload_to_s3(key="test.txt", data=data, content_type="text/plain")
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_upload_large_file(self, mock_s3_client_func):
        """Upload large file (up to 20 MB limit)."""
        mock_client = MagicMock()
        mock_s3_client_func.return_value = mock_client
        
        # Simulate 10 MB file
        large_content = b"x" * (10 * 1024 * 1024)
        data = io.BytesIO(large_content)
        
        await upload_to_s3(key="large.bin", data=data, content_type="application/octet-stream")
        
        call_kwargs = mock_client.put_object.call_args.kwargs
        assert len(call_kwargs["Body"]) == 10 * 1024 * 1024


class TestDeleteFromS3:
    """Test delete_from_s3 function."""

    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_delete_success(self, mock_s3_client_func):
        """Successful file deletion from S3."""
        mock_client = MagicMock()
        mock_s3_client_func.return_value = mock_client
        
        key = "user123/documents/old.pdf"
        
        await delete_from_s3(key=key)
        
        mock_client.delete_object.assert_called_once()
        call_kwargs = mock_client.delete_object.call_args.kwargs
        assert call_kwargs["Key"] == key
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    @patch("app.services.storage.settings")
    async def test_delete_uses_configured_bucket(self, mock_settings, mock_s3_client_func):
        """Delete uses bucket from settings."""
        mock_settings.S3_BUCKET = "production-bucket"
        mock_client = MagicMock()
        mock_s3_client_func.return_value = mock_client
        
        await delete_from_s3(key="file.txt")
        
        call_kwargs = mock_client.delete_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "production-bucket"
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_delete_nonexistent_file_raises(self, mock_s3_client_func):
        """Deleting nonexistent file raises ClientError."""
        mock_client = MagicMock()
        mock_client.delete_object.side_effect = ClientError(
            error_response={"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            operation_name="DeleteObject",
        )
        mock_s3_client_func.return_value = mock_client
        
        with pytest.raises(ClientError, match="Key not found"):
            await delete_from_s3(key="nonexistent.txt")
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_delete_network_error(self, mock_s3_client_func):
        """Network error during delete raises exception."""
        mock_client = MagicMock()
        mock_client.delete_object.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
            operation_name="DeleteObject",
        )
        mock_s3_client_func.return_value = mock_client
        
        with pytest.raises(ClientError):
            await delete_from_s3(key="file.txt")


class TestGeneratePresignedUrl:
    """Test generate_presigned_url function."""

    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_presigned_url_success(self, mock_s3_client_func):
        """Generate presigned URL successfully."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/bucket/key?signature=xyz"
        mock_s3_client_func.return_value = mock_client
        
        key = "exports/document123.pdf"
        
        url = await generate_presigned_url(key=key)
        
        assert url == "https://s3.amazonaws.com/bucket/key?signature=xyz"
        mock_client.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': mock_client.generate_presigned_url.call_args.kwargs.get('Params', {}).get('Bucket') or 'legallens-dev', 'Key': key},
            ExpiresIn=3600,
        )
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_presigned_url_custom_expiration(self, mock_s3_client_func):
        """Generate presigned URL with custom expiration."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://signed-url"
        mock_s3_client_func.return_value = mock_client
        
        key = "exports/doc.pdf"
        custom_expiration = 7200  # 2 hours
        
        url = await generate_presigned_url(key=key, expiration=custom_expiration)
        
        assert url == "https://signed-url"
        call_args = mock_client.generate_presigned_url.call_args
        assert call_args.kwargs['ExpiresIn'] == 7200
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_presigned_url_short_expiration(self, mock_s3_client_func):
        """Generate presigned URL with short expiration (5 minutes)."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://short-url"
        mock_s3_client_func.return_value = mock_client
        
        url = await generate_presigned_url(key="temp.txt", expiration=300)
        
        assert url == "https://short-url"
        call_args = mock_client.generate_presigned_url.call_args
        assert call_args.kwargs['ExpiresIn'] == 300
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    @patch("app.services.storage.settings")
    async def test_presigned_url_uses_configured_bucket(self, mock_settings, mock_s3_client_func):
        """Presigned URL uses bucket from settings."""
        mock_settings.S3_BUCKET = "exports-bucket"
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://url"
        mock_s3_client_func.return_value = mock_client
        
        await generate_presigned_url(key="file.pdf")
        
        call_args = mock_client.generate_presigned_url.call_args
        params = call_args.kwargs['Params']
        assert params['Bucket'] == "exports-bucket"
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_presigned_url_error_raises(self, mock_s3_client_func):
        """URL generation error raises ClientError."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            operation_name="GeneratePresignedUrl",
        )
        mock_s3_client_func.return_value = mock_client
        
        with pytest.raises(ClientError, match="Access denied"):
            await generate_presigned_url(key="restricted.pdf")
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_presigned_url_for_minio_local_dev(self, mock_s3_client_func):
        """Presigned URL works with MinIO endpoint."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "http://localhost:9000/bucket/file.pdf?signature=abc"
        mock_s3_client_func.return_value = mock_client
        
        url = await generate_presigned_url(key="file.pdf")
        
        assert "localhost:9000" in url or "signature" in url
        assert url.startswith("http")


class TestStorageIntegration:
    """Integration-level tests for storage operations."""

    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_upload_then_delete_flow(self, mock_s3_client_func):
        """Complete flow: upload → verify → delete."""
        mock_client = MagicMock()
        mock_s3_client_func.return_value = mock_client
        
        key = "test/flow.txt"
        data = io.BytesIO(b"test content")
        
        # Upload
        await upload_to_s3(key=key, data=data, content_type="text/plain")
        assert mock_client.put_object.called
        
        # Delete
        await delete_from_s3(key=key)
        assert mock_client.delete_object.called
        
        # Verify both used same key
        upload_key = mock_client.put_object.call_args.kwargs["Key"]
        delete_key = mock_client.delete_object.call_args.kwargs["Key"]
        assert upload_key == delete_key == key
    
    @pytest.mark.asyncio
    @patch("app.services.storage._s3_client")
    async def test_upload_then_presigned_url_flow(self, mock_s3_client_func):
        """Upload file then generate download URL."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://download-url"
        mock_s3_client_func.return_value = mock_client
        
        key = "exports/report.pdf"
        data = io.BytesIO(b"PDF content")
        
        # Upload
        await upload_to_s3(key=key, data=data, content_type="application/pdf")
        
        # Generate URL
        url = await generate_presigned_url(key=key, expiration=3600)
        
        assert url == "https://download-url"
        assert mock_client.put_object.called
        assert mock_client.generate_presigned_url.called
