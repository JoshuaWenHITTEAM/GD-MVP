from __future__ import annotations

from pathlib import Path
from typing import Dict, Generator, Optional, Union

import cv2
import numpy as np

from .yolo_model import PathLike, YoloDetector


_DETECTOR_CACHE: Dict[str, YoloDetector] = {}


def _cache_key(config_path: Optional[PathLike], model_key: Optional[str]) -> str:
    normalized_config = str(Path(config_path).resolve()) if config_path else "default"
    normalized_model = model_key or "default"
    return f"{normalized_config}:{normalized_model}"


def get_detector(
    config_path: Optional[PathLike] = None,
    model_key: Optional[str] = None,
    reload: bool = False,
) -> YoloDetector:
    key = _cache_key(config_path, model_key)
    if reload or key not in _DETECTOR_CACHE:
        _DETECTOR_CACHE[key] = YoloDetector(config_path=config_path, model_key=model_key)
    return _DETECTOR_CACHE[key]


def detect(
    input_data: Union[PathLike, np.ndarray],
    conf_threshold: float = 0.5,
    config_path: Optional[PathLike] = None,
    model_key: Optional[str] = None,
) -> list[dict]:
    """
    输入: 图像路径或 numpy 帧
    输出: 检测结果列表
    """

    detector = get_detector(config_path=config_path, model_key=model_key)
    return detector.detect(input_data=input_data, conf_threshold=conf_threshold)


def detect_video(
    input_source: Union[int, PathLike, cv2.VideoCapture],
    conf_threshold: float = 0.5,
    config_path: Optional[PathLike] = None,
    model_key: Optional[str] = None,
    frame_stride: Optional[int] = None,
) -> Generator[dict, None, None]:
    detector = get_detector(config_path=config_path, model_key=model_key)
    yield from detector.detect_video(
        input_source=input_source,
        conf_threshold=conf_threshold,
        frame_stride=frame_stride,
    )
