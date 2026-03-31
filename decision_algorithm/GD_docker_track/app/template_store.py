import base64
from dataclasses import dataclass
from threading import Lock
from typing import Optional

import cv2
import numpy as np
import torch

from app.inference.io_utils import encode_rgb_to_jpeg_bytes

EXEMPLAR_SIZE = 127
INSTANCE_SIZE = 255
CONTEXT_AMOUNT = 0.5


@dataclass
class CachedTemplate:
    template_rgb: np.ndarray
    exemplar_feat: torch.Tensor
    template_bbox_xyxy: list[int]
    current_bbox_xyxy: list[int]
    center_pos: np.ndarray
    target_size: np.ndarray
    z_size: float
    x_size: float
    channel_average: np.ndarray
    cache_version: int
    frame_index: int
    last_score: Optional[float]


class TemplateStore:
    def __init__(self):
        self._lock = Lock()
        self._cached: Optional[CachedTemplate] = None
        self._version = 0

    def set(self, image_rgb: np.ndarray, bbox_xyxy: list[int], model, force_replace: bool = True) -> CachedTemplate:
        x1, y1, x2, y2 = normalize_bbox_xyxy(bbox_xyxy, image_rgb.shape[:2])
        target_w = max(1.0, float(x2 - x1))
        target_h = max(1.0, float(y2 - y1))
        center_pos = np.array([(x1 + x2) / 2.0, (y1 + y2) / 2.0], dtype=np.float32)
        target_size = np.array([target_w, target_h], dtype=np.float32)
        channel_average = image_rgb.mean(axis=(0, 1))

        z_size = compute_context_size(target_size)
        x_size = z_size * (INSTANCE_SIZE / EXEMPLAR_SIZE)
        template_rgb = crop_and_resize(image_rgb, center_pos, z_size, EXEMPLAR_SIZE, channel_average)
        exemplar_tensor = to_tensor(template_rgb, next(model.parameters()).device)

        with torch.no_grad():
            exemplar_feat = model.feature(exemplar_tensor)

        with self._lock:
            if self._cached is not None and not force_replace:
                raise ValueError("template already exists; use replace interface to overwrite it")

            self._version += 1
            self._cached = CachedTemplate(
                template_rgb=template_rgb,
                exemplar_feat=exemplar_feat,
                template_bbox_xyxy=[x1, y1, x2, y2],
                current_bbox_xyxy=[x1, y1, x2, y2],
                center_pos=center_pos,
                target_size=target_size,
                z_size=float(z_size),
                x_size=float(x_size),
                channel_average=channel_average,
                cache_version=self._version,
                frame_index=0,
                last_score=None,
            )
            return self._cached

    def get(self) -> CachedTemplate:
        with self._lock:
            if self._cached is None:
                raise ValueError("template cache is empty; call template set interface first")
            return self._cached

    def update_tracking_state(
        self,
        center_pos: np.ndarray,
        target_size: np.ndarray,
        z_size: float,
        x_size: float,
        bbox_xyxy: list[int],
        score: float,
    ) -> CachedTemplate:
        with self._lock:
            if self._cached is None:
                raise ValueError("template cache is empty; call template set interface first")

            self._cached.center_pos = center_pos.astype(np.float32)
            self._cached.target_size = target_size.astype(np.float32)
            self._cached.z_size = float(z_size)
            self._cached.x_size = float(x_size)
            self._cached.current_bbox_xyxy = bbox_xyxy
            self._cached.last_score = float(score)
            self._cached.frame_index += 1
            return self._cached

    def summary(self):
        with self._lock:
            if self._cached is None:
                return {
                    "template_cached": False,
                    "cache_version": 0,
                    "template_bbox_xyxy": None,
                    "current_bbox_xyxy": None,
                    "current_target_size": None,
                    "frame_index": 0,
                    "last_score": None,
                }
            return {
                "template_cached": True,
                "cache_version": self._cached.cache_version,
                "template_bbox_xyxy": list(self._cached.template_bbox_xyxy),
                "current_bbox_xyxy": list(self._cached.current_bbox_xyxy),
                "current_target_size": [int(round(self._cached.target_size[0])), int(round(self._cached.target_size[1]))],
                "frame_index": self._cached.frame_index,
                "last_score": self._cached.last_score,
                "cached_template_base64": base64.b64encode(encode_rgb_to_jpeg_bytes(self._cached.template_rgb)).decode("utf-8"),
                "cached_media_type": "image/jpeg",
            }


def normalize_bbox_xyxy(bbox_xyxy: list[int], image_shape) -> list[int]:
    if len(bbox_xyxy) != 4:
        raise ValueError("bbox_xyxy must contain four integers: [x1, y1, x2, y2]")

    h, w = image_shape
    x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
    x1 = max(0, min(w - 1, x1))
    x2 = max(0, min(w - 1, x2))
    y1 = max(0, min(h - 1, y1))
    y2 = max(0, min(h - 1, y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("bbox_xyxy is invalid after clipping")
    return [x1, y1, x2, y2]


def compute_context_size(target_size: np.ndarray) -> float:
    target_w, target_h = target_size.tolist()
    context = CONTEXT_AMOUNT * (target_w + target_h)
    return float(np.sqrt((target_w + context) * (target_h + context)))


def crop_and_resize(
    image_rgb: np.ndarray,
    center_pos: np.ndarray,
    crop_size: float,
    output_size: int,
    border_value: np.ndarray,
) -> np.ndarray:
    crop_size = max(2.0, float(crop_size))
    c = (crop_size + 1.0) / 2.0
    context_xmin = int(np.floor(center_pos[0] - c + 0.5))
    context_ymin = int(np.floor(center_pos[1] - c + 0.5))
    context_xmax = context_xmin + int(round(crop_size)) - 1
    context_ymax = context_ymin + int(round(crop_size)) - 1

    left_pad = max(0, -context_xmin)
    top_pad = max(0, -context_ymin)
    right_pad = max(0, context_xmax - image_rgb.shape[1] + 1)
    bottom_pad = max(0, context_ymax - image_rgb.shape[0] + 1)

    if any(v > 0 for v in (left_pad, top_pad, right_pad, bottom_pad)):
        image_rgb = cv2.copyMakeBorder(
            image_rgb,
            top_pad,
            bottom_pad,
            left_pad,
            right_pad,
            cv2.BORDER_CONSTANT,
            value=[float(v) for v in border_value],
        )

    context_xmin += left_pad
    context_xmax += left_pad
    context_ymin += top_pad
    context_ymax += top_pad

    patch = image_rgb[context_ymin : context_ymax + 1, context_xmin : context_xmax + 1]
    if patch.size == 0:
        raise ValueError("failed to crop search/template patch from image")
    if patch.shape[0] != output_size or patch.shape[1] != output_size:
        patch = cv2.resize(patch, (output_size, output_size), interpolation=cv2.INTER_LINEAR)
    return patch


def to_tensor(image_rgb: np.ndarray, device) -> torch.Tensor:
    tensor = torch.from_numpy(image_rgb).permute(2, 0, 1).float() / 255.0
    return tensor.unsqueeze(0).to(device)


template_store = TemplateStore()
