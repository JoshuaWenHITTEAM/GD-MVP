from urllib.request import Request, urlopen

import cv2
import numpy as np

from app.schemas import PreprocessInput


def load_image_to_rgb(req: PreprocessInput) -> np.ndarray:
    provided = [
        req.image_url is not None,
        req.image_bytes is not None,
        req.image_array is not None,
        req.image_pil is not None,
    ]
    if sum(provided) != 1:
        raise ValueError("exactly one of image_url/image_bytes/image_array/image_pil must be provided")

    if req.image_url is not None:
        request = Request(req.image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as resp:
            data = resp.read()
        return decode_image_bytes_to_rgb(data, "image_url")

    if req.image_bytes is not None:
        return decode_image_bytes_to_rgb(req.image_bytes, "image_bytes")

    if req.image_array is not None:
        img = req.image_array
        if img.ndim != 3 or img.shape[2] != 3:
            raise ValueError("image_array must be HWC with 3 channels")
        if img.dtype != np.uint8:
            img = np.clip(img, 0, 255).astype(np.uint8)
        return img

    return np.array(req.image_pil.convert("RGB"))


def decode_image_bytes_to_rgb(data: bytes, source_name: str) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"failed to decode image from {source_name}")
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def ensure_uint8_rgb(image_rgb: np.ndarray) -> np.ndarray:
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError("processed image must be HWC with 3 channels")

    if image_rgb.dtype == np.uint8:
        return image_rgb

    if np.issubdtype(image_rgb.dtype, np.floating):
        if image_rgb.max() <= 1.0:
            image_rgb = image_rgb * 255.0
        image_rgb = np.clip(image_rgb, 0, 255)
        return image_rgb.astype(np.uint8)

    return np.clip(image_rgb, 0, 255).astype(np.uint8)


def encode_rgb_to_jpeg_bytes(image_rgb: np.ndarray, quality: int = 90) -> bytes:
    image_rgb = ensure_uint8_rgb(image_rgb)
    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("failed to encode processed image to jpeg")
    return buf.tobytes()

