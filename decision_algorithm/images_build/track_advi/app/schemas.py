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
    initial_bbox_xyxy: list[int]
    template_size: list[int]
    cached_template_base64: Optional[bytes] = None
    cached_media_type: Optional[str] = "image/jpeg"


@dataclass
class TrackOutput:
    cache_version: int
    frame_index: int
    bbox_xyxy: list[int]
    score: float
    tracked_image_bytes: Optional[bytes] = None
    tracked_media_type: Optional[str] = "image/jpeg"
    timings_ms: Optional[dict[str, float]] = None


class URLImageRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    image_url: str
    return_image: bool = True


class TemplateURLRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    image_url: str
    initial_bbox_xyxy: list[int]
    return_image: bool = True
