from __future__ import annotations

import json
import os
import uuid as py_uuid
from typing import List, Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.database import AlgorithmResult, MediaAsset
from app.services.asset_service import asset_service


class ResultService:
    def upload_result(
        self,
        db: Session,
        file: UploadFile,
        source_asset_uuid: py_uuid.UUID,
        result_type: str,
        metrics_json: Optional[str],
        extra_json: Optional[str],
    ) -> AlgorithmResult:
        source_asset = asset_service.get_asset_or_404(db, source_asset_uuid)
        if source_asset.status == 'deleted':
            raise HTTPException(status_code=400, detail='Source asset is deleted')
        if not file.filename:
            raise HTTPException(status_code=400, detail='Uploaded result file must have a filename')

        temp_path = asset_service._save_to_temp(file)
        try:
            local_file_size = os.path.getsize(temp_path)
            bucket_name = asset_service.get_bucket('result')
            object_key = f'results/{source_asset.uuid}/{py_uuid.uuid4().hex}_{file.filename}'

            metrics = json.loads(metrics_json) if metrics_json else {}
            extra = json.loads(extra_json) if extra_json else {}
            if not isinstance(metrics, dict):
                raise HTTPException(status_code=400, detail='metrics_json must be a JSON object')
            if not isinstance(extra, dict):
                raise HTTPException(status_code=400, detail='extra_json must be a JSON object')

            result_asset = MediaAsset(
                original_name=file.filename,
                media_type='result',
                content_type=file.content_type,
                bucket_name=bucket_name,
                object_key=object_key,
                file_size=local_file_size,
                etag=None,
                status='uploading',
                dataset_name=source_asset.dataset_name,
                source_label='algorithm-output',
                split=source_asset.split,
                sequence_name=source_asset.sequence_name,
                modality=source_asset.modality,
                previewable=True,
            )
            db.add(result_asset)
            db.commit()
            db.refresh(result_asset)

            put_ret = asset_service.minio_service.upload_file(bucket_name, object_key, temp_path, file.content_type)
            stat = asset_service.minio_service.client.stat_object(bucket_name, object_key)

            result_asset.file_size = int(getattr(stat, 'size', local_file_size))
            result_asset.etag = getattr(put_ret, 'etag', None)
            result_asset.status = 'active'
            db.commit()
            db.refresh(result_asset)

            algorithm_result = AlgorithmResult(
                source_asset_id=source_asset.id,
                result_asset_id=result_asset.id,
                result_type=result_type,
                metrics=metrics,
                extra=extra,
            )
            db.add(algorithm_result)
            db.commit()
            db.refresh(algorithm_result)

            stmt = (
                select(AlgorithmResult)
                .options(selectinload(AlgorithmResult.result_asset), selectinload(AlgorithmResult.source_asset))
                .where(AlgorithmResult.id == algorithm_result.id)
            )
            created = db.scalar(stmt)
            if not created:
                raise HTTPException(status_code=500, detail='Result created but failed to reload')
            return created
        except Exception:
            if 'result_asset' in locals() and getattr(result_asset, 'id', None) is not None:
                try:
                    result_asset.status = 'failed'
                    db.commit()
                except Exception:
                    db.rollback()
            raise
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def get_result_or_404(self, db: Session, result_uuid: py_uuid.UUID) -> AlgorithmResult:
        stmt = (
            select(AlgorithmResult)
            .options(selectinload(AlgorithmResult.result_asset), selectinload(AlgorithmResult.source_asset))
            .where(AlgorithmResult.uuid == result_uuid)
        )
        result = db.scalar(stmt)
        if not result:
            raise HTTPException(status_code=404, detail='Result not found')
        return result

    def list_results_for_asset(self, db: Session, source_asset_uuid: py_uuid.UUID) -> List[AlgorithmResult]:
        source_asset = asset_service.get_asset_or_404(db, source_asset_uuid)
        stmt = (
            select(AlgorithmResult)
            .options(selectinload(AlgorithmResult.result_asset), selectinload(AlgorithmResult.source_asset))
            .where(AlgorithmResult.source_asset_id == source_asset.id)
            .order_by(AlgorithmResult.created_at.desc())
        )
        return list(db.scalars(stmt).all())

    def result_to_dict(self, result: AlgorithmResult) -> dict:
        return {
            'uuid': str(result.uuid),
            'sourceAssetUuid': str(result.source_asset.uuid),
            'resultAssetUuid': str(result.result_asset.uuid),
            'resultType': result.result_type,
            'metrics': result.metrics or {},
            'extra': result.extra or {},
            'createdAt': result.created_at.isoformat() if result.created_at else None,
            'resultAsset': asset_service.asset_to_dict(result.result_asset),
        }


result_service = ResultService()
