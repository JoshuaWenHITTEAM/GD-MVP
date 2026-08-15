from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.response import success
from app.services.asset_service import asset_service


router = APIRouter(prefix='/algorithm', tags=['algorithm'])


@router.get('/manifest')
def get_manifest(
    dataset_name: Optional[str] = None,
    media_type: Optional[str] = None,
    split: Optional[str] = None,
    sequence_name: Optional[str] = None,
    modality: Optional[str] = None,
    pageNum: int = 1,
    pageSize: int = 1000,
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    total, items = asset_service.list_assets(
        db,
        media_type,
        dataset_name,
        'active',
        None,
        pageNum,
        pageSize,
        split=split,
        sequence_name=sequence_name,
        modality=modality,
    )
    return success({
        'items': [asset_service.asset_to_dict(item) for item in items],
        'total': total,
        'pageNum': pageNum,
        'pageSize': pageSize,
    })


@router.get('/assets/{asset_uuid}/content')
def proxy_download_content(
    asset_uuid: uuid.UUID,
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    asset = asset_service.get_asset_or_404(db, asset_uuid)
    try:
        response = asset_service.minio_service.get_object_stream(asset.bucket_name, asset.object_key)
        return StreamingResponse(
            response.stream(32 * 1024),
            media_type=asset.content_type or 'application/octet-stream',
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
