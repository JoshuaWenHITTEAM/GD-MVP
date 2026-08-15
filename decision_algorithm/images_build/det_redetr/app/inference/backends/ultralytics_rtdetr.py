import os

from app.inference.io_utils import build_yolo_txt, encode_bgr_to_jpeg_bytes
from app.schemas import InferOutput


DEFAULT_CONF = float(os.getenv("RTDETR_CONF", "0.25"))
DEFAULT_IOU = float(os.getenv("RTDETR_IOU", "0.45"))
DEFAULT_IMGSZ = int(os.getenv("RTDETR_IMGSZ", "640"))
DEFAULT_MAX_DET = int(os.getenv("RTDETR_MAX_DET", "300"))


def _keep_top1_result(result):
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) <= 1:
        return result
    top_index = int(boxes.conf.argmax().item())
    return result[top_index]


def run_rtdetr_detect(
    model,
    image_bgr,
    model_name: str,
    *,
    return_image: bool,
    return_yolo_txt: bool,
) -> InferOutput:
    results = model.predict(
        source=image_bgr,
        conf=DEFAULT_CONF,
        iou=DEFAULT_IOU,
        imgsz=DEFAULT_IMGSZ,
        max_det=DEFAULT_MAX_DET,
        verbose=False,
    )
    if not results:
        raise ValueError("model returned empty results")

    result = _keep_top1_result(results[0].cpu())
    detections = result.summary(normalize=False, decimals=5)
    yolo_txt = build_yolo_txt(result) if return_yolo_txt else None
    annotated_image_bytes = None
    annotated_media_type = None
    if return_image:
        annotated_bgr = result.plot()
        annotated_image_bytes = encode_bgr_to_jpeg_bytes(annotated_bgr)
        annotated_media_type = "image/jpeg"

    return InferOutput(
        model_name=model_name,
        num_detections=len(detections),
        detections=detections,
        yolo_txt=yolo_txt,
        annotated_image_bytes=annotated_image_bytes,
        annotated_media_type=annotated_media_type,
    )
