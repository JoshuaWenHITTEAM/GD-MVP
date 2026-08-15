from __future__ import annotations

from typing import Set

from sqlalchemy import inspect

from app.core.database import engine


REQUIRED_MEDIA_ASSET_COLUMNS: Set[str] = {
    'id',
    'uuid',
    'original_name',
    'media_type',
    'content_type',
    'bucket_name',
    'object_key',
    'file_size',
    'etag',
    'status',
    'created_at',
    'updated_at',
    'dataset_name',
    'split',
    'sequence_name',
    'modality',
    'previewable',
}


REQUIRED_ALGORITHM_RESULT_COLUMNS: Set[str] = {
    'id',
    'uuid',
    'source_asset_id',
    'result_asset_id',
    'result_type',
    'metrics',
    'extra',
    'created_at',
}


def validate_schema() -> None:
    inspector = inspect(engine)

    if not inspector.has_table('media_asset'):
        raise RuntimeError('media_asset 表不存在，请先执行 sql/001_migrate_media_asset_for_api.sql')

    media_columns = {col['name'] for col in inspector.get_columns('media_asset')}
    missing_media_columns = REQUIRED_MEDIA_ASSET_COLUMNS - media_columns
    if missing_media_columns:
        raise RuntimeError(
            'media_asset 表缺少字段: '
            + ', '.join(sorted(missing_media_columns))
            + '。请先执行 sql/001_migrate_media_asset_for_api.sql'
        )

    if inspector.has_table('algorithm_result'):
        result_columns = {col['name'] for col in inspector.get_columns('algorithm_result')}
        missing_result_columns = REQUIRED_ALGORITHM_RESULT_COLUMNS - result_columns
        if missing_result_columns:
            raise RuntimeError(
                'algorithm_result 表缺少字段: '
                + ', '.join(sorted(missing_result_columns))
                + '。请先执行 sql/002_create_algorithm_result.sql'
            )
