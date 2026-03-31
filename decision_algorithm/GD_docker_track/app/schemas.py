from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict


@dataclass
class TemplateInput:
    initial_bbox_xyxy: list[int]
    image_url: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_array: Optional[np.ndarray] = None
    image_pil: Optional[Image.Image] = None


@dataclass
class TrackInput:
    image_url: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_array: Optional[np.ndarray] = None
    image_pil: Optional[Image.Image] = None


@dataclass
class TemplateOutput:
    status: str
    cache_version: int
    initial_bbox_xyxy: list[int]
    template_size: list[int]
    cached_template_base64: bytes
    cached_media_type: str = "image/jpeg"


@dataclass
class TrackOutput:
    cache_version: int
    frame_index: int
    bbox_xyxy: list[int]
    score: float
    tracked_image_bytes: bytes
    tracked_media_type: str = "image/jpeg"


class URLImageRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    image_url: str


class TemplateURLRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    image_url: str
    initial_bbox_xyxy: list[int]
