from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import List, Optional, Set

import torch

from app.inference.backends.siamrpnpp_runtime import SiamRPNPPRuntime


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHT_ROOT = Path(os.getenv("WEIGHT_ROOT", "/models"))
FALLBACK_WEIGHT_ROOT = PROJECT_ROOT / "models"
DEFAULT_WEIGHT_NAME = os.getenv("DEFAULT_WEIGHT_NAME", "siamrpnpp.pth")
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "siamrpnpp.yaml"

_MODEL_CACHE: Optional[SiamRPNPPRuntime] = None
_MODEL_LOCK = Lock()


def weight_roots() -> List[Path]:
    roots: List[Path] = []
    for candidate in (DEFAULT_WEIGHT_ROOT, FALLBACK_WEIGHT_ROOT):
        if candidate not in roots:
            roots.append(candidate)
    return roots


def get_weight_path() -> Path:
    checked_paths: List[str] = []
    for root in weight_roots():
        candidate = root / DEFAULT_WEIGHT_NAME
        checked_paths.append(str(candidate))
        if candidate.exists():
            return candidate
    raise ValueError(f"weight file not found, checked paths={checked_paths}")


def get_model() -> SiamRPNPPRuntime:
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    with _MODEL_LOCK:
        if _MODEL_CACHE is not None:
            return _MODEL_CACHE
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        _MODEL_CACHE = SiamRPNPPRuntime(
            config_path=DEFAULT_CONFIG_PATH,
            weight_path=get_weight_path(),
            device=device,
        )
        return _MODEL_CACHE


def current_device_info() -> dict[str, object]:
    cuda_available = torch.cuda.is_available()
    cuda_device_count = torch.cuda.device_count() if cuda_available else 0
    if _MODEL_CACHE is not None:
        device = _MODEL_CACHE.device
        return {
            "device": str(device),
            "torch_cuda_available": cuda_available,
            "cuda_device_count": cuda_device_count,
        }
    return {
        "device": "cuda:0" if cuda_available else "cpu",
        "torch_cuda_available": cuda_available,
        "cuda_device_count": cuda_device_count,
    }


def health_info():
    available_weights: Set[str] = set()
    for root in weight_roots():
        if root.exists():
            available_weights.update(path.name for path in root.glob("*.pth"))
            available_weights.update(path.name for path in root.glob("*.pt"))
    return {
        "weight_root": str(DEFAULT_WEIGHT_ROOT),
        "fallback_weight_root": str(FALLBACK_WEIGHT_ROOT),
        "default_weight_name": DEFAULT_WEIGHT_NAME,
        "default_config_path": str(DEFAULT_CONFIG_PATH),
        "available_weights": sorted(available_weights),
        "model_cached": _MODEL_CACHE is not None,
        "cached_models": [DEFAULT_WEIGHT_NAME] if _MODEL_CACHE is not None else [],
        **current_device_info(),
    }
