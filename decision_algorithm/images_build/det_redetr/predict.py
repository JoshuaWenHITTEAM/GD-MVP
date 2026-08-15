from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import torch
import yaml
from ultralytics import RTDETR


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_from_base(raw_path: Optional[str], base_dir: Path) -> Optional[Path]:
    if not raw_path:
        return None
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def resolve_runtime_path(cli_value: Optional[str], config_value: Optional[str], config_dir: Path) -> Optional[Path]:
    if cli_value:
        return Path(cli_value).expanduser().resolve()
    return resolve_from_base(config_value, config_dir)


def to_uint8_image(array: np.ndarray) -> np.ndarray:
    if array.dtype == np.uint8:
        return array

    array = np.nan_to_num(array)
    array_min = float(array.min())
    array_max = float(array.max())
    if array_max <= array_min:
        return np.zeros(array.shape, dtype=np.uint8)

    normalized = (array - array_min) / (array_max - array_min)
    return (normalized * 255.0).clip(0, 255).astype(np.uint8)


def load_image(image_path: Path) -> np.ndarray:
    if not image_path.exists():
        raise FileNotFoundError(f"Input image does not exist: {image_path}")

    if image_path.suffix.lower() == ".npy":
        image = np.load(image_path)
        if image.ndim == 3 and image.shape[0] in {1, 3} and image.shape[-1] not in {1, 3}:
            image = np.transpose(image, (1, 2, 0))
        if image.ndim == 2:
            image = cv2.cvtColor(to_uint8_image(image), cv2.COLOR_GRAY2BGR)
        elif image.ndim == 3 and image.shape[-1] == 1:
            image = cv2.cvtColor(to_uint8_image(image[..., 0]), cv2.COLOR_GRAY2BGR)
        elif image.ndim == 3 and image.shape[-1] == 3:
            image = to_uint8_image(image)
        else:
            raise ValueError(f"Unsupported numpy image shape: {image.shape}")
        return image

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Unable to read image: {image_path}")
    return image


def select_device(raw_device: Any) -> Any:
    requested = str(raw_device or "auto")
    if requested == "auto":
        return 0 if torch.cuda.is_available() else "cpu"
    return raw_device


def format_detections(result: Any) -> List[Dict[str, Any]]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    names = result.names
    xyxy_list = boxes.xyxy.cpu().tolist()
    xywh_list = boxes.xywh.cpu().tolist()
    conf_list = boxes.conf.cpu().tolist()
    cls_list = boxes.cls.cpu().tolist()

    detections: List[Dict[str, Any]] = []
    for xyxy, xywh, score, class_id in zip(xyxy_list, xywh_list, conf_list, cls_list):
        class_index = int(class_id)
        class_name = names[class_index] if isinstance(names, list) else str(names.get(class_index, class_index))
        detections.append(
            {
                "class_id": class_index,
                "class_name": class_name,
                "score": float(score),
                "bbox_xyxy": {
                    "x1": float(xyxy[0]),
                    "y1": float(xyxy[1]),
                    "x2": float(xyxy[2]),
                    "y2": float(xyxy[3]),
                },
                "bbox_xywh": {
                    "x": float(xywh[0]),
                    "y": float(xywh[1]),
                    "w": float(xywh[2]),
                    "h": float(xywh[3]),
                },
            }
        )
    return detections


def draw_detections(
    image: np.ndarray,
    detections: List[Dict[str, Any]],
    color: List[int],
    line_thickness: int,
    font_scale: float,
) -> np.ndarray:
    canvas = image.copy()
    box_color = tuple(int(value) for value in color)
    for item in detections:
        bbox = item["bbox_xyxy"]
        x1 = int(round(bbox["x1"]))
        y1 = int(round(bbox["y1"]))
        x2 = int(round(bbox["x2"]))
        y2 = int(round(bbox["y2"]))
        label = f'{item["class_name"]}:{item["score"]:.3f}'
        cv2.rectangle(canvas, (x1, y1), (x2, y2), box_color, line_thickness)
        cv2.putText(
            canvas,
            label,
            (x1, max(y1 - 8, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            box_color,
            max(line_thickness - 1, 1),
            cv2.LINE_AA,
        )
    return canvas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-image RT-DETR prediction entrypoint.")
    parser.add_argument("--config", type=Path, default=Path("configs/predict.yaml"), help="Prediction config path.")
    parser.add_argument("--input", type=str, default=None, help="Image path override.")
    parser.add_argument("--output-json", type=str, default=None, help="Prediction JSON path override.")
    parser.add_argument("--output-image", type=str, default=None, help="Visualization image path override.")
    parser.add_argument("--conf", type=float, default=None, help="Confidence threshold override.")
    parser.add_argument("--device", type=str, default=None, help="Device override, for example '0' or 'cpu'.")
    parser.add_argument("--no-save-image", action="store_true", help="Disable saving visualization image.")
    parser.add_argument("--no-save-json", action="store_true", help="Disable saving prediction JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.expanduser().resolve()
    config = load_yaml(config_path)
    config_dir = config_path.parent

    model_cfg = dict(config.get("model", {}))
    input_cfg = dict(config.get("input", {}))
    output_cfg = dict(config.get("output", {}))
    vis_cfg = dict(config.get("visualization", {}))

    weights_path = resolve_from_base(model_cfg.get("weights"), config_dir)
    if weights_path is None:
        raise ValueError(f"No model.weights configured in {config_path}")
    if not weights_path.exists():
        raise FileNotFoundError(f"Model weights do not exist: {weights_path}")

    input_path = resolve_runtime_path(args.input, input_cfg.get("image_path"), config_dir)
    if input_path is None:
        raise ValueError("Prediction input is required. Set input.image_path in config or pass --input.")

    output_json_path = resolve_runtime_path(args.output_json, output_cfg.get("json_path"), config_dir)
    output_image_path = resolve_runtime_path(args.output_image, output_cfg.get("image_path"), config_dir)

    save_json = bool(output_cfg.get("save_json", True)) and not args.no_save_json
    save_image = bool(output_cfg.get("save_image", True)) and not args.no_save_image
    print_json = bool(output_cfg.get("print_json", True))

    conf_threshold = float(args.conf if args.conf is not None else model_cfg.get("conf", 0.25))
    iou_threshold = float(model_cfg.get("iou", 0.45))
    imgsz = int(model_cfg.get("imgsz", 640))
    max_det = int(model_cfg.get("max_det", 300))
    device = select_device(args.device if args.device is not None else model_cfg.get("device", "auto"))

    image = load_image(input_path)
    model = RTDETR(str(weights_path))
    predictions = model.predict(
        source=image,
        conf=conf_threshold,
        iou=iou_threshold,
        imgsz=imgsz,
        max_det=max_det,
        device=device,
        verbose=False,
    )
    detections = format_detections(predictions[0] if predictions else None)

    result = {
        "input_path": str(input_path),
        "weights_path": str(weights_path),
        "image_size": {
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
        },
        "num_detections": len(detections),
        "detections": detections,
    }

    if save_image:
        if output_image_path is None:
            raise ValueError("output.image_path must be configured when save_image is enabled.")
        vis_image = draw_detections(
            image=image,
            detections=detections,
            color=list(vis_cfg.get("box_color_bgr", [0, 215, 255])),
            line_thickness=int(vis_cfg.get("line_thickness", 2)),
            font_scale=float(vis_cfg.get("font_scale", 0.55)),
        )
        output_image_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_image_path), vis_image)
        result["saved_image_path"] = str(output_image_path)

    if save_json:
        if output_json_path is None:
            raise ValueError("output.json_path must be configured when save_json is enabled.")
        result["saved_json_path"] = str(output_json_path)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    if print_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
