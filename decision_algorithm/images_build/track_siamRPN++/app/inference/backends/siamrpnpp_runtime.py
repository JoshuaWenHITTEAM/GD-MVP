from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import torch

from pysot.core.config import cfg
from pysot.models.model_builder import ModelBuilder
from pysot.tracker.tracker_builder import build_tracker
from pysot.utils.model_load import load_pretrain


@dataclass
class PreparedTemplate:
    template_rgb: np.ndarray
    template_bbox_xyxy: list[int]
    template_size: list[int]


@dataclass
class TrackStep:
    bbox_xyxy: list[int]
    score: float


class SiamRPNPPRuntime:
    def __init__(self, config_path: Path, weight_path: Path, device: torch.device):
        self.config_path = config_path
        self.weight_path = weight_path
        self.device = device
        self._lock = Lock()
        self._tracker = None
        self.min_track_score = float(os.getenv("SIAMRPNPP_MIN_SCORE", "0.60"))

        cfg.merge_from_file(str(config_path))
        cfg.CUDA = device.type == "cuda"
        if device.type != "cuda":
            thread_count = self._resolve_cpu_threads()
            if thread_count is not None:
                torch.set_num_threads(thread_count)
        else:
            torch.backends.cudnn.benchmark = True

        model = ModelBuilder()
        model = load_pretrain(model, str(weight_path))
        self.model = model.eval().to(device)

    def _resolve_cpu_threads(self) -> int | None:
        raw_value = os.getenv("SIAMRPNPP_NUM_THREADS", "").strip()
        if raw_value:
            try:
                parsed = int(raw_value)
            except ValueError:
                parsed = 0
            if parsed > 0:
                return parsed
        cpu_total = os.cpu_count() or 1
        return max(1, min(cpu_total, 8))

    def prepare_template(self, image_rgb: np.ndarray, bbox_xyxy: list[int]) -> PreparedTemplate:
        image_h, image_w = image_rgb.shape[:2]
        clipped = self._clip_bbox_xyxy(bbox_xyxy, image_w, image_h)
        tracker = build_tracker(self.model)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        bbox_xywh = self._xyxy_to_xywh(clipped)
        with self._lock:
            with torch.inference_mode():
                tracker.init(image_bgr, bbox_xywh)
            self._tracker = tracker

        x1, y1, x2, y2 = clipped
        template_rgb = image_rgb[y1:y2, x1:x2].copy()
        return PreparedTemplate(
            template_rgb=template_rgb,
            template_bbox_xyxy=clipped,
            template_size=[x2 - x1, y2 - y1],
        )

    def track(self, image_rgb: np.ndarray) -> TrackStep:
        if self._tracker is None:
            raise ValueError("template cache is empty; call template set interface first")

        image_h, image_w = image_rgb.shape[:2]
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        with self._lock:
            prev_center = self._tracker.center_pos.copy()
            prev_size = self._tracker.size.copy()
            with torch.inference_mode():
                outputs = self._tracker.track(image_bgr)
            score = float(outputs["best_score"])
            if score < self.min_track_score:
                self._tracker.center_pos = prev_center
                self._tracker.size = prev_size
                prev_bbox = [
                    float(prev_center[0] - prev_size[0] / 2),
                    float(prev_center[1] - prev_size[1] / 2),
                    float(prev_size[0]),
                    float(prev_size[1]),
                ]
                bbox_xyxy = self._xywh_to_xyxy(prev_bbox, image_w, image_h)
                return TrackStep(
                    bbox_xyxy=bbox_xyxy,
                    score=score,
                )

        bbox_xyxy = self._xywh_to_xyxy(outputs["bbox"], image_w, image_h)
        return TrackStep(
            bbox_xyxy=bbox_xyxy,
            score=score,
        )

    def _clip_bbox_xyxy(self, bbox_xyxy: list[int], image_w: int, image_h: int) -> list[int]:
        x1, y1, x2, y2 = [int(round(v)) for v in bbox_xyxy]
        x1 = max(0, min(image_w - 1, x1))
        y1 = max(0, min(image_h - 1, y1))
        x2 = max(x1 + 1, min(image_w, x2))
        y2 = max(y1 + 1, min(image_h, y2))
        return [x1, y1, x2, y2]

    def _xyxy_to_xywh(self, bbox_xyxy: list[int]) -> list[float]:
        x1, y1, x2, y2 = bbox_xyxy
        return [float(x1), float(y1), float(max(1, x2 - x1)), float(max(1, y2 - y1))]

    def _xywh_to_xyxy(self, bbox_xywh: list[float], image_w: int, image_h: int) -> list[int]:
        x, y, w, h = bbox_xywh
        x1 = int(round(max(0.0, min(image_w - 1.0, x))))
        y1 = int(round(max(0.0, min(image_h - 1.0, y))))
        x2 = int(round(max(float(x1 + 1), min(float(image_w), x + w))))
        y2 = int(round(max(float(y1 + 1), min(float(image_h), y + h))))
        return [x1, y1, x2, y2]
