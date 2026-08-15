from typing import Union
from urllib.request import Request, urlopen

import cv2
import numpy as np

from app.schemas import TemplateInput, TrackInput


def load_image_to_rgb(req: Union[TemplateInput, TrackInput]) -> np.ndarray:
    provided = [
        req.image_url is not None,
        req.image_bytes is not None,
        req.image_array is not None,
        req.image_pil is not None,
    ]
    if sum(provided) != 1:
        raise ValueError("exactly one image source must be provided")

    if req.image_url is not None:
        request = Request(req.image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as resp:
            data = resp.read()
        return decode_image_bytes_to_rgb(data, "image_url")

    if req.image_bytes is not None:
        return decode_image_bytes_to_rgb(req.image_bytes, "image_bytes")

    if req.image_array is not None:
        img = req.image_array
        if img.dtype != np.uint8:
            img = np.clip(img, 0, 255).astype(np.uint8)
        if img.ndim == 2:
            return img
        if img.ndim == 3 and img.shape[2] == 1:
            return img[:, :, 0]
        if img.ndim != 3 or img.shape[2] != 3:
            raise ValueError("image_array must be HW grayscale or HWC with 1/3 channels")
        return img

    return np.array(req.image_pil.convert("RGB"))


def decode_image_bytes_to_rgb(data: bytes, source_name: str) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"failed to decode image from {source_name}")
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def encode_rgb_to_jpeg_bytes(image_rgb: np.ndarray, quality: int = 90) -> bytes:
    image_rgb = np.clip(image_rgb, 0, 255).astype(np.uint8)
    if image_rgb.ndim == 2:
        image_bgr = image_rgb
    else:
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("failed to encode image to jpeg")
    return buf.tobytes()


def annotate_bbox(image_rgb: np.ndarray, bbox_xyxy: list[int], color=(255, 0, 0), thickness: int = 3) -> np.ndarray:
    if image_rgb.ndim == 2:
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_GRAY2BGR)
    else:
        image_bgr = cv2.cvtColor(image_rgb.copy(), cv2.COLOR_RGB2BGR)
    x1, y1, x2, y2 = bbox_xyxy
    cv2.rectangle(image_bgr, (x1, y1), (x2, y2), color[::-1], thickness)
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
