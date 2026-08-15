from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict


@dataclass
class TemplateInput:
    initial_bbox_xyxy: List[int]
    image_url: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_array: Optional[np.ndarray] = None
    image_pil: Optional[Image.Image] = None
    return_image: bool = True


@dataclass
class TrackInput:
    image_url: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_array: Optional[np.ndarray] = None
    image_pil: Optional[Image.Image] = None
    return_image: bool = True


@dataclass
class TemplateOutput:
    status: str
    cache_version: int
    initial_bbox_xyxy: List[int]
    template_size: List[int]
    cached_template_base64: Optional[bytes] = None
    cached_media_type: Optional[str] = "image/jpeg"


@dataclass
class TrackOutput:
    cache_version: int
    frame_index: int
    bbox_xyxy: List[int]
    score: float
    tracked_image_bytes: Optional[bytes] = None
    tracked_media_type: Optional[str] = "image/jpeg"


class URLImageRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    image_url: str
    return_image: bool = True


class TemplateURLRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    image_url: str
    initial_bbox_xyxy: List[int]
    return_image: bool = True
