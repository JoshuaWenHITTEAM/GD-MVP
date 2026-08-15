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

import importlib.util
import sys
from pathlib import Path

import numpy as np

MIDDLE_OBJ_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MIDDLE_OBJ_DIR.parents[2]
SDK_DIR = MIDDLE_OBJ_DIR / "sdk" / "python"
PROJECT_SDK_DIR = PROJECT_ROOT / "sdk" / "python"
MIDWARE_PATH = SDK_DIR / "midware.py"

if not MIDWARE_PATH.is_file():
    raise FileNotFoundError(f"midware.py not found: {MIDWARE_PATH}")

for sdk_path in (PROJECT_SDK_DIR, SDK_DIR):
    sdk_path_str = str(sdk_path)
    if sdk_path.is_dir() and sdk_path_str not in sys.path:
        sys.path.insert(0, sdk_path_str)

_MIDWARE_SPEC = importlib.util.spec_from_file_location("algorithm_chain_server_midware", MIDWARE_PATH)
if _MIDWARE_SPEC is None or _MIDWARE_SPEC.loader is None:
    raise ImportError(f"failed to create import spec for: {MIDWARE_PATH}")

_MIDWARE_MODULE = importlib.util.module_from_spec(_MIDWARE_SPEC)
sys.modules.setdefault("algorithm_chain_server_midware", _MIDWARE_MODULE)
_MIDWARE_SPEC.loader.exec_module(_MIDWARE_MODULE)

ShmConsumer = _MIDWARE_MODULE.ShmConsumer
TYPE_IMAGE_FRAME = _MIDWARE_MODULE.TYPE_IMAGE_FRAME
TYPE_RDMA_IMAGE_RAW = _MIDWARE_MODULE.TYPE_RDMA_IMAGE_RAW
rebuild_rdma_image = _MIDWARE_MODULE.rebuild_rdma_image


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
            image_bytes = rebuild_rdma_image(pkt.payload)
        except ValueError:
            return IMAGE_READ_ERROR
    else:
        return IMAGE_READ_ERROR

    if len(image_bytes) < _EXPECTED_SIZE:
        return IMAGE_READ_ERROR

    return image_bytes[:_EXPECTED_SIZE]


def get_raw_image():
    """
    Read one image packet from /dev/shm/shm-cons-sim-2 and return the original
    1024x1024 uint8 image values, or IMAGE_READ_ERROR when no image is available.

    This function has no parameters by design and does not block.
    """
    image_bytes = _try_read_raw_image_bytes()
    if isinstance(image_bytes, int) and image_bytes == IMAGE_READ_ERROR:
        return IMAGE_READ_ERROR
    return np.frombuffer(image_bytes, dtype=np.uint8).reshape((_IMAGE_H, _IMAGE_W)).copy()


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
