from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict

from app.schemas.asset import AssetResponse


class AlgorithmResultResponse(BaseModel):
    uuid: uuid.UUID
    sourceAssetUuid: uuid.UUID
    resultAssetUuid: uuid.UUID
    resultType: str
    metrics: Dict[str, Any]
    extra: Dict[str, Any]
    createdAt: datetime
    resultAsset: AssetResponse

    model_config = ConfigDict(from_attributes=True)


class AlgorithmResultListData(BaseModel):
    items: List[AlgorithmResultResponse]
    total: int
