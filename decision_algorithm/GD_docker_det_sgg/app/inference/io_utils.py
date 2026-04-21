from urllib.request import Request, urlopen

import cv2
import numpy as np

from app.schemas import InferInput


def load_image_to_bgr(req: InferInput) -> np.ndarray:
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
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("failed to decode image from image_url")
        return img

    if req.image_bytes is not None:
        arr = np.frombuffer(req.image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("failed to decode image from image_bytes")
        return img

    if req.image_array is not None:
        img = req.image_array
        if img.ndim != 3 or img.shape[2] != 3:
            raise ValueError("image_array must be HWC with 3 channels")
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)
        return img

    rgb = np.array(req.image_pil.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def build_yolo_txt(result) -> str:
    if result.boxes is None or len(result.boxes) == 0:
        return ""

    result = result.cpu()
    boxes = result.boxes

    cls_list = boxes.cls.tolist()
    conf_list = boxes.conf.tolist()
    xywhn_list = boxes.xywhn.tolist()

    lines = []
    for cls_id, xywhn, conf in zip(cls_list, xywhn_list, conf_list):
        lines.append(
            f"{int(cls_id)} "
            f"{xywhn[0]:.6f} {xywhn[1]:.6f} {xywhn[2]:.6f} {xywhn[3]:.6f} "
            f"{conf:.6f}"
        )
    return "\n".join(lines)


def encode_bgr_to_jpeg_bytes(image_bgr, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("failed to encode annotated image to jpeg")
    return buf.tobytes()