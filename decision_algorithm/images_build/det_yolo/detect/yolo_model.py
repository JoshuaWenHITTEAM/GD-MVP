from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import cv2
import numpy as np
import torch
import yaml

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - dependency availability is environment-specific
    YOLO = None


PathLike = Union[str, os.PathLike[str]]


@dataclass
class DetectionResult:
    x: float
    y: float
    w: float
    h: float
    score: float
    class_id: int
    class_name: str
    model_key: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": {
                "x": self.x,
                "y": self.y,
                "w": self.w,
                "h": self.h,
            },
            "score": self.score,
            "class_id": self.class_id,
            "class": self.class_name,
            "model": self.model_key,
        }


class YoloDetector:
    def __init__(
        self,
        config_path: Optional[PathLike] = None,
        model_key: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config_path = Path(config_path) if config_path else Path(__file__).with_name("config.yaml")
        self.config = self._load_config(self.config_path)
        self.package_dir = self.config_path.parent
        self.runtime_cfg = dict(self.config.get("runtime", {}))
        self.models_cfg = dict(self.config.get("models", {}))
        self.model_key = model_key or self.runtime_cfg.get("default_model", "default")
        self.model_cfg = dict(self.models_cfg.get(self.model_key, {}))
        if not self.model_cfg:
            raise KeyError(f"Model '{self.model_key}' is not defined in {self.config_path}")

        self.overrides = overrides or {}
        self.default_conf_threshold = float(
            self.overrides.get("conf_threshold", self.runtime_cfg.get("conf_threshold", 0.35))
        )
        self.default_iou_threshold = float(
            self.overrides.get("iou_threshold", self.runtime_cfg.get("iou_threshold", 0.45))
        )
        self.default_frame_stride = int(
            self.overrides.get("frame_stride", self.runtime_cfg.get("frame_stride", 1))
        )
        self.device = self._select_device()
        self.model_source = self._resolve_model_source()
        self._model = None
        self._class_id_cache: Optional[List[int]] = None

    @staticmethod
    def _load_config(config_path: Path) -> Dict[str, Any]:
        with config_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _select_device(self) -> str:
        requested_device = str(
            self.overrides.get("device", os.getenv("DETECT_DEVICE", self.runtime_cfg.get("device", "auto")))
        )
        if requested_device == "auto":
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        if requested_device.startswith("cuda") and not torch.cuda.is_available():
            return "cpu"
        return requested_device

    def _resolve_model_source(self) -> str:
        env_override = os.getenv("YOLO_MODEL_PATH")
        if env_override:
            candidate = Path(env_override)
            return str(candidate if candidate.is_absolute() else (Path.cwd() / candidate).resolve())

        configured_weights = self.model_cfg.get("weights")
        resolved: Optional[Path] = None
        if configured_weights:
            candidate = Path(configured_weights)
            resolved = candidate if candidate.is_absolute() else (self.package_dir / candidate).resolve()
            if resolved.exists():
                return str(resolved)

        fallback_weights = self.model_cfg.get("fallback_weights")
        if fallback_weights:
            return str(fallback_weights)

        if resolved is not None:
            return str(resolved)
        raise ValueError(f"No weights configured for model '{self.model_key}'")

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        if YOLO is None:
            raise ImportError(
                "ultralytics is not installed. Install dependencies from requirements.txt before running detection."
            )

        try:
            self._model = YOLO(self.model_source)
        except Exception as exc:  # pragma: no cover - network / checkpoint failure depends on runtime
            raise RuntimeError(
                "Unable to initialize YOLO model. Place a compatible weight file under detect/weights or set YOLO_MODEL_PATH."
            ) from exc

        return self._model

    def _resolve_target_class_ids(self) -> Optional[List[int]]:
        if self._class_id_cache is not None:
            return self._class_id_cache

        model = self._load_model()
        names = model.names
        if isinstance(names, list):
            class_map = {name: index for index, name in enumerate(names)}
        else:
            class_map = {str(name): int(index) for index, name in names.items()}

        target_classes = self.model_cfg.get("target_classes") or []
        class_ids: List[int] = []
        for target_class in target_classes:
            target_key = str(target_class).strip()
            if not target_key:
                continue
            if target_key.isdigit():
                class_ids.append(int(target_key))
            elif target_key in class_map:
                class_ids.append(class_map[target_key])
        self._class_id_cache = class_ids or None
        return self._class_id_cache

    def _predict(self, source: Union[PathLike, np.ndarray], conf_threshold: Optional[float]) -> Any:
        model = self._load_model()
        kwargs: Dict[str, Any] = {
            "conf": float(conf_threshold if conf_threshold is not None else self.default_conf_threshold),
            "iou": self.default_iou_threshold,
            "device": self.device,
            "verbose": False,
        }
        imgsz = self.model_cfg.get("imgsz")
        if imgsz:
            kwargs["imgsz"] = int(imgsz)

        target_class_ids = self._resolve_target_class_ids()
        if target_class_ids:
            kwargs["classes"] = target_class_ids

        return model.predict(source=source, **kwargs)

    def detect(self, input_data: Union[PathLike, np.ndarray], conf_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        predictions = self._predict(input_data, conf_threshold=conf_threshold)
        if not predictions:
            return []
        return self._format_predictions(predictions[0])

    def detect_video(
        self,
        input_source: Union[int, PathLike, cv2.VideoCapture],
        conf_threshold: Optional[float] = None,
        frame_stride: Optional[int] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        capture, should_release = self._open_video_capture(input_source)
        stride = max(int(frame_stride or self.default_frame_stride), 1)
        frame_index = -1
        try:
            while True:
                has_frame, frame = capture.read()
                if not has_frame:
                    break
                frame_index += 1
                if frame_index % stride != 0:
                    continue
                yield {
                    "frame_index": frame_index,
                    "detections": self.detect(frame, conf_threshold=conf_threshold),
                    "frame": frame,
                }
        finally:
            if should_release:
                capture.release()

    def _open_video_capture(
        self, input_source: Union[int, PathLike, cv2.VideoCapture]
    ) -> Tuple[cv2.VideoCapture, bool]:
        if isinstance(input_source, cv2.VideoCapture):
            return input_source, False
        capture = cv2.VideoCapture(input_source)
        if not capture.isOpened():
            raise ValueError(f"Unable to open video source: {input_source}")
        return capture, True

    def _format_predictions(self, prediction: Any) -> List[Dict[str, Any]]:
        names = prediction.names
        boxes = getattr(prediction, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return []

        detections: List[Dict[str, Any]] = []
        xywh_list = boxes.xywh.cpu().tolist()
        conf_list = boxes.conf.cpu().tolist()
        cls_list = boxes.cls.cpu().tolist()
        for xywh, score, class_id in zip(xywh_list, conf_list, cls_list):
            class_index = int(class_id)
            class_name = names[class_index] if isinstance(names, list) else str(names.get(class_index, class_index))
            detection = DetectionResult(
                x=float(xywh[0]),
                y=float(xywh[1]),
                w=float(xywh[2]),
                h=float(xywh[3]),
                score=float(score),
                class_id=class_index,
                class_name=class_name,
                model_key=self.model_key,
            )
            detections.append(detection.to_dict())
        return detections
