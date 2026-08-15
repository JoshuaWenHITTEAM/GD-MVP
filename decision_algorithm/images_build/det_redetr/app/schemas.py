from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict


@dataclass
class InferInput:
    model_name: str
    image_url: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_array: Optional[np.ndarray] = None
    image_pil: Optional[Image.Image] = None
    return_image: bool = True
    return_yolo_txt: bool = True


@dataclass
class InferOutput:
    model_name: str
    num_detections: int
    detections: list[dict]
    yolo_txt: Optional[str] = None
    annotated_image_bytes: Optional[bytes] = None
    annotated_media_type: Optional[str] = "image/jpeg"


class URLInferRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_name: str
    image_url: str
    return_image: bool = True
    return_yolo_txt: bool = True
