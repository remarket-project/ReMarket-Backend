"""MinIO/S3 Object Storage Service"""

import io
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minio import Minio
    from minio.error import S3Error
else:
    try:
        from minio import Minio
        from minio.error import S3Error
    except ImportError:
        Minio = None  # type: ignore
        S3Error = None  # type: ignore

from app.core.config import settings


class MinIOService:
    """Service for managing file uploads to MinIO"""

    def __init__(self):
        if not settings.use_minio:
            raise RuntimeError("MinIO is not configured")

        self.client = Minio(
            settings.MINIO_ENDPOINT,  # type: ignore[arg-type]
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist and set public policy"""
        import json
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)

            # Set bucket policy to public read
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                    }
                ]
            }
            self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
        except S3Error as e:
            print(f"Error creating/configuring bucket: {e}")

    def upload_file(
        self,
        file_path: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file to MinIO

        Args:
            file_path: Path in MinIO (e.g., "listings/uuid.jpg")
            file_data: File content as bytes
            content_type: MIME type

        Returns:
            URL to access the file
        """
        try:
            self.client.put_object(
                self.bucket_name,
                file_path,
                io.BytesIO(file_data),
                len(file_data),
                content_type=content_type,
            )

            # Generate public URL if endpoint is configured
            if settings.MINIO_PUBLIC_ENDPOINT:
                endpoint = settings.MINIO_PUBLIC_ENDPOINT.rstrip("/")
                return f"{endpoint}/{self.bucket_name}/{file_path}"

            # Generate presigned URL (valid for 7 days)
            url = self.client.get_presigned_url(
                "GET",
                self.bucket_name,
                file_path,
                expires=timedelta(days=7),
            )
            return url
        except S3Error as e:
            print(f"Error uploading file: {e}")
            raise

    def delete_file(self, file_path: str) -> bool:
        """Delete file from MinIO"""
        try:
            self.client.remove_object(self.bucket_name, file_path)
            return True
        except S3Error as e:
            print(f"Error deleting file: {e}")
            return False

    def get_presigned_url(
        self, file_path: str, expires: timedelta | None = None
    ) -> str:
        """Get presigned URL or public URL for file"""
        if settings.MINIO_PUBLIC_ENDPOINT:
            endpoint = settings.MINIO_PUBLIC_ENDPOINT.rstrip("/")
            return f"{endpoint}/{self.bucket_name}/{file_path}"

        if expires is None:
            expires = timedelta(days=7)

        try:
            return self.client.get_presigned_url(
                "GET",
                self.bucket_name,
                file_path,
                expires=expires,
            )
        except S3Error as e:
            print(f"Error generating URL: {e}")
            raise


# Singleton instance
_minio_service: MinIOService | None = None


def get_minio_service() -> MinIOService | None:
    """Get or create MinIO service instance"""
    global _minio_service
    if _minio_service is None and settings.use_minio:
        _minio_service = MinIOService()
        _minio_service.ensure_bucket_exists()
    return _minio_service
