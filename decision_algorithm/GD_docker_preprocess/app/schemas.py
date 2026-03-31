from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict


@dataclass
class PreprocessInput:
    method_name: str
    image_url: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_array: Optional[np.ndarray] = None
    image_pil: Optional[Image.Image] = None


@dataclass
class PreprocessOutput:
    method_name: str
    processed_image_bytes: bytes
    processed_media_type: str = "image/jpeg"


class URLPreprocessRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    method_name: str
    image_url: str

