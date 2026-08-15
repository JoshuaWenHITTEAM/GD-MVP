import cv2

from app.inference.io_utils import encode_bgr_to_jpeg_bytes
from app.schemas import InferOutput


def run_unsharp(image_bgr, model_name: str, *, return_image: bool) -> InferOutput:
    gaussian = cv2.GaussianBlur(image_bgr, (0, 0), sigmaX=1.2, sigmaY=1.2)
    processed = cv2.addWeighted(image_bgr, 1.6, gaussian, -0.6, 0)

    return InferOutput(
        model_name="hot_test_1",
        operation="unsharp",
        processed_image_bytes=encode_bgr_to_jpeg_bytes(processed) if return_image else None,
        processed_media_type="image/jpeg",
        metadata={
            "sigma": 1.2,
            "alpha": 1.6,
            "beta": -0.6,
        },
    )
