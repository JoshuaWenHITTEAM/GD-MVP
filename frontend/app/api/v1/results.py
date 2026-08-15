from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.response import success
from app.services.result_service import result_service


router = APIRouter(prefix='/results', tags=['results'])


@router.post('/upload')
def upload_result(
    file: UploadFile = File(...),
    source_asset_uuid: uuid.UUID = Form(...),
    result_type: str = Form(...),
    metrics_json: Optional[str] = Form(default=None),
    extra_json: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(verify_api_key),
):
    result = result_service.upload_result(db, file, source_asset_uuid, result_type, metrics_json, extra_json)
    return success(result_service.result_to_dict(result))


@router.get('/{result_uuid}')
def get_result(result_uuid: uuid.UUID, db: Session = Depends(get_db)):
    result = result_service.get_result_or_404(db, result_uuid)
    return success(result_service.result_to_dict(result))
