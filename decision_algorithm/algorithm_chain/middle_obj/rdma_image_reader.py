#!/usr/bin/env python3
"""
Fixed RDMA image reader for downstream algorithms.

Usage:
    from rdma_image_reader import IMAGE_READ_ERROR, get_image

    image = get_image()
    if isinstance(image, int) and image == IMAGE_READ_ERROR:
        # no image is available now
        pass
"""

import sys
import time
from pathlib import Path

import numpy as np

MIDDLE_OBJ_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MIDDLE_OBJ_DIR.parents[2]
SDK_DIR = MIDDLE_OBJ_DIR / "sdk" / "python"
PROJECT_SDK_DIR = PROJECT_ROOT / "sdk" / "python"

for sdk_path in reversed((SDK_DIR, PROJECT_SDK_DIR)):
    sdk_path_str = str(sdk_path)
    if sdk_path.is_dir() and sdk_path_str not in sys.path:
        sys.path.insert(0, sdk_path_str)

from midware import ShmConsumer, TYPE_IMAGE_FRAME, TYPE_RDMA_IMAGE_RAW, rebuild_rdma_image  # noqa: E402


_SHM_PATH = "/dev/shm/shm-cons-sim-2"
_IMAGE_W = 1024
_IMAGE_H = 1024
_EXPECTED_SIZE = _IMAGE_W * _IMAGE_H
IMAGE_READ_ERROR = -1

_consumer = None


def _get_consumer():
    global _consumer
    if _consumer is None:
        _consumer = ShmConsumer(_SHM_PATH)
    return _consumer


def _try_read_raw_image_bytes():
    rebuild_image_ms = 0.0
    try:
        consumer = _get_consumer()
        pkt = consumer.read_latest_packet()
    except Exception:
        return IMAGE_READ_ERROR

    if pkt is None:
        return IMAGE_READ_ERROR

    if pkt.type == TYPE_IMAGE_FRAME:
        image_bytes = pkt.payload
    elif pkt.type == TYPE_RDMA_IMAGE_RAW:
        try:
            rebuild_started_at = time.perf_counter()
            image_bytes = rebuild_rdma_image(pkt.payload)
            rebuild_image_ms = (time.perf_counter() - rebuild_started_at) * 1000.0
        except ValueError:
            return IMAGE_READ_ERROR
    else:
        return IMAGE_READ_ERROR

    if len(image_bytes) < _EXPECTED_SIZE:
        return IMAGE_READ_ERROR

    return image_bytes[:_EXPECTED_SIZE], pkt, rebuild_image_ms


def get_raw_image():
    """
    Read one image packet from /dev/shm/shm-cons-sim-2 and return the original
    1024x1024 uint8 image values, or IMAGE_READ_ERROR when no image is available.

    This function has no parameters by design and does not block.
    """
    result = _try_read_raw_image_bytes()
    if isinstance(result, int) and result == IMAGE_READ_ERROR:
        return IMAGE_READ_ERROR
    image_bytes, _, _ = result
    return np.frombuffer(image_bytes, dtype=np.uint8).reshape((_IMAGE_H, _IMAGE_W)).copy()


def get_image_frame():
    """
    Read the latest image packet and return a dict containing the image and
    middleware timing metadata, or IMAGE_READ_ERROR when no image is available.

    This is the same timing surface used by the online chain; camera timing
    tests should prefer this over calling the SDK rebuild path independently.
    """
    started_at = time.perf_counter()
    result = _try_read_raw_image_bytes()
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0
    if isinstance(result, int) and result == IMAGE_READ_ERROR:
        return IMAGE_READ_ERROR

    image_bytes, pkt, rebuild_image_ms = result
    image = np.frombuffer(image_bytes, dtype=np.uint8).reshape((_IMAGE_H, _IMAGE_W)).copy()
    timestamp_us = int(getattr(pkt, "timestamp_us", 0) or 0)
    middleware_age_ms = None
    if timestamp_us >= 1_000_000_000_000_000:
        middleware_age_ms = (time.time_ns() // 1000 - timestamp_us) / 1000.0

    return {
        "image": image,
        "timestamp_us": timestamp_us,
        "type": int(getattr(pkt, "type", -1)),
        "payload_len": int(getattr(pkt, "payload_len", len(getattr(pkt, "payload", b"")))),
        "read_packet_ms": elapsed_ms,
        "decode_packet_ms": elapsed_ms,
        "rebuild_image_ms": rebuild_image_ms,
        "middleware_age_ms": middleware_age_ms,
    }


def get_image():
    """
    Read one image packet from /dev/shm/shm-cons-sim-2 and return a display-ready
    1024x1024 uint8 image, or IMAGE_READ_ERROR when no image is available.

    This matches the viewer behavior: type=3 packets are rebuilt first, then the
    image is stretched to 0..255 using its current min/max values.
    """
    img = get_raw_image()
    if isinstance(img, int) and img == IMAGE_READ_ERROR:
        return IMAGE_READ_ERROR
    min_v = int(img.min())
    max_v = int(img.max())
    if max_v > min_v:
        img = ((img.astype(np.uint16) - min_v) * 255 // (max_v - min_v)).astype(np.uint8)
    return img


if __name__ == "__main__":
    image = get_image()
    if isinstance(image, int) and image == IMAGE_READ_ERROR:
        print("image read failed")
    else:
        print(f"image shape={image.shape}, dtype={image.dtype}, min={image.min()}, max={image.max()}")
