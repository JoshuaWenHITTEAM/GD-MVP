from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.response import success
from app.services.asset_service import asset_service
from app.services.result_service import result_service


router = APIRouter(prefix='/assets', tags=['assets'])


@router.post('/upload')
def upload_asset(
    file: UploadFile = File(...),
    media_type: str = Form(...),
    dataset_name: Optional[str] = Form(default=None),
    split: Optional[str] = Form(default=None),
    sequence_name: Optional[str] = Form(default=None),
    modality: Optional[str] = Form(default=None),
    previewable: Optional[bool] = Form(default=None),
    db: Session = Depends(get_db),
):
    asset = asset_service.upload_asset(
        db,
        file,
        media_type,
        dataset_name,
        split=split,
        sequence_name=sequence_name,
        modality=modality,
        previewable=previewable,
    )
    return success(asset_service.asset_to_dict(asset))


@router.get('')
def list_assets(
    media_type: Optional[str] = None,
    dataset_name: Optional[str] = None,
    status: Optional[str] = 'active',
    keyword: Optional[str] = None,
    split: Optional[str] = None,
    sequence_name: Optional[str] = None,
    modality: Optional[str] = None,
    previewable: Optional[bool] = None,
    pageNum: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
):
    total, items = asset_service.list_assets(
        db,
        media_type,
        dataset_name,
        status,
        keyword,
        pageNum,
        pageSize,
        split=split,
        sequence_name=sequence_name,
        modality=modality,
        previewable=previewable,
    )
    return success({
        'items': [asset_service.asset_to_dict(item) for item in items],
        'total': total,
        'pageNum': pageNum,
        'pageSize': pageSize,
    })


@router.get('/{asset_uuid}')
def get_asset(asset_uuid: uuid.UUID, db: Session = Depends(get_db)):
    asset = asset_service.get_asset_or_404(db, asset_uuid)
    return success(asset_service.asset_to_dict(asset))


@router.delete('/{asset_uuid}')
def delete_asset(asset_uuid: uuid.UUID, db: Session = Depends(get_db)):
    asset = asset_service.logical_delete(db, asset_uuid)
    return success({'uuid': str(asset.uuid), 'status': asset.status})


@router.get('/{asset_uuid}/preview-url')
def get_preview_url(asset_uuid: uuid.UUID, db: Session = Depends(get_db)):
    url = asset_service.get_preview_url(db, asset_uuid, None)
    return success({'uuid': str(asset_uuid), 'url': url, 'expiresIn': 1800})


@router.get('/{asset_uuid}/download-url')
def get_download_url(asset_uuid: uuid.UUID, db: Session = Depends(get_db)):
    url = asset_service.get_download_url(db, asset_uuid, None)
    return success({'uuid': str(asset_uuid), 'url': url, 'expiresIn': 1800})


@router.get('/{asset_uuid}/results')
def list_results_for_asset(asset_uuid: uuid.UUID, db: Session = Depends(get_db)):
    results = result_service.list_results_for_asset(db, asset_uuid)
    return success({
        'items': [result_service.result_to_dict(item) for item in results],
        'total': len(results),
    })
