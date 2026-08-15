from __future__ import annotations

from datetime import timedelta
from typing import Optional

from minio import Minio

from app.core.config import get_settings


settings = get_settings()


class MinioService:
    def __init__(self) -> None:
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self, bucket_name: str) -> None:
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)

    def ensure_required_buckets(self) -> None:
        for bucket_name in settings.required_buckets:
            self.ensure_bucket(bucket_name)

    def upload_file(self, bucket_name: str, object_key: str, file_path: str, content_type: Optional[str] = None):
        return self.client.fput_object(
            bucket_name=bucket_name,
            object_name=object_key,
            file_path=file_path,
            content_type=content_type,
        )

    def presigned_get_url(
        self,
        bucket_name: str,
        object_key: str,
        expires_seconds: Optional[int] = None,
        download_name: Optional[str] = None,
    ) -> str:
        effective_expires = expires_seconds or settings.presigned_url_expire_seconds
        response_headers = None
        if download_name:
            response_headers = {
                'response-content-disposition': f'attachment; filename="{download_name}"'
            }
        return self.client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_key,
            expires=timedelta(seconds=effective_expires),
            response_headers=response_headers,
        )

    def get_object_stream(self, bucket_name: str, object_key: str):
        return self.client.get_object(bucket_name, object_key)

    def list_objects(self, bucket_name: str, prefix: str = '', recursive: bool = True):
        return self.client.list_objects(
            bucket_name=bucket_name,
            prefix=prefix,
            recursive=recursive,
        )


_minio_service: Optional[MinioService] = None


def get_minio_service() -> MinioService:
    global _minio_service
    if _minio_service is None:
        _minio_service = MinioService()
    return _minio_service
