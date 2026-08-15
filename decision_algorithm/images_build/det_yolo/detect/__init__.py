"""Lightweight YOLO detection module for anti-drone tasks."""

from .infer import detect, detect_video, get_detector

__all__ = ["detect", "detect_video", "get_detector"]
