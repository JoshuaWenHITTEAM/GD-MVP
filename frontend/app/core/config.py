from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / '.env'),
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    app_name: str = 'Data Platform API V3'
    debug: bool = True
    cors_allow_origins: str = '*'

    api_key: Optional[str] = None

    postgres_host: str = '127.0.0.1'
    postgres_port: int = 5432
    postgres_db: str = 'mediadb'
    postgres_user: str = 'appuser'
    postgres_password: str = ''

    minio_endpoint: str = '127.0.0.1:9000'
    minio_access_key: str = ''
    minio_secret_key: str = ''
    minio_secure: bool = False

    raw_images_bucket: str = 'raw-images'
    raw_videos_bucket: str = 'raw-videos'
    raw_annotations_bucket: str = 'raw-annotations'
    raw_metadata_bucket: str = 'raw-metadata'
    algorithm_results_bucket: str = 'algorithm-results'

    presigned_url_expire_seconds: int = 1800
    max_upload_size_mb: int = 1024

    @property
    def database_url(self) -> str:
        return (
            f'postgresql+psycopg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )

    @property
    def cors_origins(self) -> List[str]:
        values = [item.strip() for item in self.cors_allow_origins.split(',') if item.strip()]
        return values or ['*']

    @property
    def required_buckets(self) -> List[str]:
        return [
            self.raw_images_bucket,
            self.raw_videos_bucket,
            self.raw_annotations_bucket,
            self.raw_metadata_bucket,
            self.algorithm_results_bucket,
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
