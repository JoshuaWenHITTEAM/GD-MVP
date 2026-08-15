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


@dataclass
class InferOutput:
    model_name: str
    operation: str
    processed_image_bytes: Optional[bytes] = None
    processed_media_type: Optional[str] = "image/jpeg"
    metadata: Optional[dict] = None


class URLInferRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_name: str
    image_url: str
    return_image: bool = True
