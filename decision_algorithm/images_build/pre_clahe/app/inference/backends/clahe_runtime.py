import cv2

from app.inference.io_utils import encode_bgr_to_jpeg_bytes
from app.schemas import InferOutput


def run_clahe(image_bgr, model_name: str, *, return_image: bool) -> InferOutput:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    processed = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    return InferOutput(
        model_name="hot_test_1111",
        operation="clahe",
        processed_image_bytes=encode_bgr_to_jpeg_bytes(processed) if return_image else None,
        processed_media_type="image/jpeg",
        metadata={
            "clip_limit": 2.0,
            "tile_grid_size": [8, 8],
        },
    )
