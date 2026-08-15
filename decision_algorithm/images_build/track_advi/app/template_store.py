import base64
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

import numpy as np

from app.inference.io_utils import encode_rgb_to_jpeg_bytes


@dataclass
class CachedTemplate:
    template_rgb: np.ndarray
    z_dict1: Any
    template_bbox_xyxy: list[int]
    current_bbox_xyxy: list[int]
    state_xywh: list[float]
    cache_version: int
    frame_index: int
    last_score: Optional[float]


class TemplateStore:
    def __init__(self):
        self._lock = Lock()
        self._cached: Optional[CachedTemplate] = None
        self._version = 0

    def set(
        self,
        template_rgb: np.ndarray,
        z_dict1: Any,
        bbox_xyxy: list[int],
        state_xywh: list[float],
        force_replace: bool = True,
    ) -> CachedTemplate:
        with self._lock:
            if self._cached is not None and not force_replace:
                raise ValueError("template already exists; use replace interface to overwrite it")

            self._version += 1
            self._cached = CachedTemplate(
                template_rgb=template_rgb,
                z_dict1=z_dict1,
                template_bbox_xyxy=list(bbox_xyxy),
                current_bbox_xyxy=list(bbox_xyxy),
                state_xywh=list(state_xywh),
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

    def update_tracking_state(self, state_xywh: list[float], bbox_xyxy: list[int], score: float) -> CachedTemplate:
        with self._lock:
            if self._cached is None:
                raise ValueError("template cache is empty; call template set interface first")
            self._cached.state_xywh = list(state_xywh)
            self._cached.current_bbox_xyxy = list(bbox_xyxy)
            self._cached.last_score = float(score)
            self._cached.frame_index += 1
            return self._cached

    def reject_tracking_state(self, score: float) -> CachedTemplate:
        with self._lock:
            if self._cached is None:
                raise ValueError("template cache is empty; call template set interface first")
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
                    "frame_index": 0,
                    "last_score": None,
                }
            return {
                "template_cached": True,
                "cache_version": self._cached.cache_version,
                "template_bbox_xyxy": list(self._cached.template_bbox_xyxy),
                "current_bbox_xyxy": list(self._cached.current_bbox_xyxy),
                "frame_index": self._cached.frame_index,
                "last_score": self._cached.last_score,
                "cached_template_base64": base64.b64encode(
                    encode_rgb_to_jpeg_bytes(self._cached.template_rgb)
                ).decode("utf-8"),
                "cached_media_type": "image/jpeg",
            }


template_store = TemplateStore()
