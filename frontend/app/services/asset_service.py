from __future__ import annotations

import os
import tempfile
import uuid as py_uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.minio_client import get_minio_service
from app.models.database import MediaAsset

settings = get_settings()
ALLOWED_MEDIA_TYPES = {'image', 'video', 'annotation', 'metadata', 'result'}


class AssetService:
    def __init__(self):
        self.minio_service = get_minio_service()

    def get_bucket(self, media_type: str) -> str:
        mapping = {
            'image': settings.raw_images_bucket,
            'video': settings.raw_videos_bucket,
            'annotation': settings.raw_annotations_bucket,
            'metadata': settings.raw_metadata_bucket,
            'result': settings.algorithm_results_bucket,
        }
        if media_type not in mapping:
            raise HTTPException(status_code=400, detail=f'Unsupported media_type: {media_type}')
        return mapping[media_type]

    def _save_to_temp(self, upload_file: UploadFile) -> str:
        suffix = Path(upload_file.filename or '').suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            upload_file.file.seek(0)
            while True:
                chunk = upload_file.file.read(1024 * 1024)
                if not chunk:
                    break
                tmp.write(chunk)
            return tmp.name

    def _default_previewable(self, media_type: str) -> bool:
        return media_type in {'image', 'video', 'result'}

    def _build_object_key(self, media_type: str, dataset_name: Optional[str], filename: str) -> str:
        prefix = (dataset_name.strip() if dataset_name else media_type).replace(' ', '_')
        return f"{prefix}/{datetime.now():%Y/%m/%d}/{py_uuid.uuid4().hex}_{Path(filename).name}"

    def upload_asset(
        self,
        db: Session,
        file: UploadFile,
        media_type: str,
        dataset_name: Optional[str],
        split: Optional[str] = None,
        sequence_name: Optional[str] = None,
        modality: Optional[str] = None,
        previewable: Optional[bool] = None,
    ) -> MediaAsset:
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise HTTPException(status_code=400, detail='media_type must be image, video, annotation, metadata or result')
        if not file.filename:
            raise HTTPException(status_code=400, detail='Uploaded file must have a filename')

        temp_path = self._save_to_temp(file)
        try:
            local_file_size = os.path.getsize(temp_path)
            if local_file_size > settings.max_upload_size_mb * 1024 * 1024:
                raise HTTPException(status_code=413, detail=f'File too large. Max size is {settings.max_upload_size_mb} MB')

            bucket_name = self.get_bucket(media_type)
            object_key = self._build_object_key(media_type, dataset_name, file.filename)
            effective_previewable = self._default_previewable(media_type) if previewable is None else bool(previewable)

            exists_stmt = select(MediaAsset).where(
                MediaAsset.bucket_name == bucket_name,
                MediaAsset.object_key == object_key,
            )
            existed = db.scalar(exists_stmt)
            if existed:
                raise HTTPException(status_code=409, detail='Asset already exists with the same bucket/object_key')

            asset = MediaAsset(
                original_name=Path(file.filename).name,
                media_type=media_type,
                content_type=file.content_type,
                bucket_name=bucket_name,
                object_key=object_key,
                file_size=local_file_size,
                etag=None,
                status='uploading',
                dataset_name=dataset_name,
                split=split,
                sequence_name=sequence_name,
                modality=modality,
                previewable=effective_previewable,
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)

            result = self.minio_service.upload_file(bucket_name, object_key, temp_path, file.content_type)
            stat = self.minio_service.client.stat_object(bucket_name, object_key)

            asset.etag = getattr(result, 'etag', None)
            asset.file_size = int(getattr(stat, 'size', local_file_size))
            asset.status = 'active'
            db.commit()
            db.refresh(asset)
            return asset
        except Exception:
            # 占位记录已经存在时，统一标记失败，保留排障痕迹
            if 'asset' in locals() and getattr(asset, 'id', None) is not None:
                try:
                    asset.status = 'failed'
                    db.commit()
                except Exception:
                    db.rollback()
            raise
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def list_assets(
        self,
        db: Session,
        media_type: Optional[str],
        dataset_name: Optional[str],
        status_filter: Optional[str],
        keyword: Optional[str],
        page_num: int,
        page_size: int,
        split: Optional[str] = None,
        sequence_name: Optional[str] = None,
        modality: Optional[str] = None,
        previewable: Optional[bool] = None,
    ) -> Tuple[int, list[MediaAsset]]:
        stmt = select(MediaAsset)
        count_stmt = select(func.count(MediaAsset.id))
        filters = []

        if media_type:
            filters.append(MediaAsset.media_type == media_type)
        if dataset_name:
            filters.append(MediaAsset.dataset_name == dataset_name)
        if status_filter:
            filters.append(MediaAsset.status == status_filter)
        if split:
            filters.append(MediaAsset.split == split)
        if sequence_name:
            filters.append(MediaAsset.sequence_name == sequence_name)
        if modality:
            filters.append(MediaAsset.modality == modality)
        if previewable is not None:
            filters.append(MediaAsset.previewable == bool(previewable))
        if keyword:
            filters.append(or_(
                MediaAsset.original_name.ilike(f'%{keyword}%'),
                MediaAsset.object_key.ilike(f'%{keyword}%'),
            ))

        for condition in filters:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = db.scalar(count_stmt) or 0
        stmt = stmt.order_by(MediaAsset.created_at.desc()).offset((page_num - 1) * page_size).limit(page_size)
        items = list(db.scalars(stmt).all())
        return total, items

    def get_asset_or_404(self, db: Session, asset_uuid: py_uuid.UUID) -> MediaAsset:
        asset = db.scalar(select(MediaAsset).where(MediaAsset.uuid == asset_uuid))
        if not asset:
            raise HTTPException(status_code=404, detail='Asset not found')
        return asset

    def logical_delete(self, db: Session, asset_uuid: py_uuid.UUID) -> MediaAsset:
        asset = self.get_asset_or_404(db, asset_uuid)
        asset.status = 'deleted'
        db.commit()
        db.refresh(asset)
        return asset

    def get_preview_url(self, db: Session, asset_uuid: py_uuid.UUID, expires_in: Optional[int]) -> str:
        asset = self.get_asset_or_404(db, asset_uuid)
        if not asset.previewable:
            raise HTTPException(status_code=400, detail='Current asset is not previewable')

        if asset.media_type not in {'image', 'video'}:
            raise HTTPException(status_code=400, detail='Preview only supports image and video')

        return self.minio_service.presigned_get_url(asset.bucket_name, asset.object_key, expires_in)

    def get_download_url(self, db: Session, asset_uuid: py_uuid.UUID, expires_in: Optional[int]) -> str:
        asset = self.get_asset_or_404(db, asset_uuid)
        return self.minio_service.presigned_get_url(asset.bucket_name, asset.object_key, expires_in, asset.original_name)

    def asset_to_dict(self, asset: MediaAsset) -> dict:
        return {
            'uuid': str(asset.uuid),
            'original_name': asset.original_name,
            'media_type': asset.media_type,
            'content_type': asset.content_type,
            'bucket_name': asset.bucket_name,
            'object_key': asset.object_key,
            'file_size': asset.file_size,
            'etag': asset.etag,
            'status': asset.status,
            'dataset_name': asset.dataset_name,
            'split': asset.split,
            'sequence_name': asset.sequence_name,
            'modality': asset.modality,
            'previewable': asset.previewable,
            'created_at': asset.created_at.isoformat() if asset.created_at else None,
            'updated_at': asset.updated_at.isoformat() if asset.updated_at else None,
        }


asset_service = AssetService()
