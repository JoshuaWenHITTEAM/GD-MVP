import os

from app.inference.io_utils import build_yolo_txt, encode_bgr_to_jpeg_bytes
from app.schemas import InferOutput


DEFAULT_CONF = float(os.getenv("YOLO_CONF", "0.35"))
DEFAULT_IOU = float(os.getenv("YOLO_IOU", "0.45"))
DEFAULT_IMGSZ = int(os.getenv("YOLO_IMGSZ", "1280"))
DEFAULT_MAX_DET = int(os.getenv("YOLO_MAX_DET", "300"))
DEFAULT_TARGET_CLASSES = os.getenv("YOLO_TARGET_CLASSES", "")


def _model_class_map(model) -> dict[str, int]:
    names = getattr(model, "names", {}) or {}
    if isinstance(names, list):
        return {str(name).lower(): index for index, name in enumerate(names)}
    return {str(name).lower(): int(index) for index, name in names.items()}


def _resolve_target_class_ids(model) -> list[int] | None:
    raw_classes = [item.strip() for item in DEFAULT_TARGET_CLASSES.split(",") if item.strip()]
    if not raw_classes:
        return None

    class_map = _model_class_map(model)
    class_ids: list[int] = []
    missing: list[str] = []
    for raw_class in raw_classes:
        if raw_class.isdigit():
            class_ids.append(int(raw_class))
            continue

        class_id = class_map.get(raw_class.lower())
        if class_id is None:
            missing.append(raw_class)
        else:
            class_ids.append(class_id)

    if missing:
        available = ", ".join(sorted(class_map)) or "<unknown>"
        raise ValueError(f"target classes not found in model names: {missing}; available={available}")

    return sorted(set(class_ids))


def _keep_top1_result(result):
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) <= 1:
        return result
    top_index = int(boxes.conf.argmax().item())
    return result[top_index]


def run_ultralytics_detect(
    model,
    image_bgr,
    model_name: str,
    *,
    return_image: bool,
    return_yolo_txt: bool,
) -> InferOutput:
    target_class_ids = _resolve_target_class_ids(model)
    predict_kwargs = {}
    if target_class_ids is not None:
        predict_kwargs["classes"] = target_class_ids

    results = model.predict(
        source=image_bgr,
        conf=DEFAULT_CONF,
        iou=DEFAULT_IOU,
        imgsz=DEFAULT_IMGSZ,
        max_det=DEFAULT_MAX_DET,
        verbose=False,
        **predict_kwargs,
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
