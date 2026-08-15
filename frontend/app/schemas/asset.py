from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AssetResponse(BaseModel):
    uuid: uuid.UUID
    original_name: str
    media_type: str
    content_type: Optional[str] = None
    bucket_name: str
    object_key: str
    file_size: Optional[int] = None
    etag: Optional[str] = None
    status: str
    dataset_name: Optional[str] = None
    split: Optional[str] = None
    sequence_name: Optional[str] = None
    modality: Optional[str] = None
    previewable: Optional[bool] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AssetListData(BaseModel):
    items: List[AssetResponse]
    total: int
    pageNum: int
    pageSize: int


class PresignedUrlData(BaseModel):
    uuid: uuid.UUID
    url: str
    expiresIn: int


class DeleteAssetData(BaseModel):
    uuid: uuid.UUID
    status: str


class UploadAssetData(AssetResponse):
    pass
