import os
from pathlib import Path
from threading import Lock

import torch
from ultralytics import RTDETR


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHT_ROOT = Path(os.getenv("WEIGHT_ROOT", "/models"))
FALLBACK_WEIGHT_ROOT = PROJECT_ROOT / "models"

_MODEL_CACHE: dict[str, RTDETR] = {}
_MODEL_LOCK = Lock()


def normalize_model_name(model_name: str) -> str:
    if not model_name or not model_name.strip():
        raise ValueError("model_name is empty")

    safe_name = model_name.strip()
    if safe_name.endswith(".pt"):
        safe_name = safe_name[:-3]
    return safe_name


def weight_roots() -> list[Path]:
    roots: list[Path] = []
    for candidate in (DEFAULT_WEIGHT_ROOT, FALLBACK_WEIGHT_ROOT):
        if candidate not in roots:
            roots.append(candidate)
    return roots


def get_weight_path(model_name: str) -> Path:
    safe_name = normalize_model_name(model_name)
    checked_paths: list[str] = []
    for root in weight_roots():
        weight_path = root / f"{safe_name}.pt"
        checked_paths.append(str(weight_path))
        if weight_path.exists():
            return weight_path

    raise ValueError(
        f"weight file not found for model_name='{safe_name}', checked paths={checked_paths}"
    )


def get_model(model_name: str) -> RTDETR:
    safe_name = normalize_model_name(model_name)
    if safe_name in _MODEL_CACHE:
        return _MODEL_CACHE[safe_name]

    with _MODEL_LOCK:
        if safe_name in _MODEL_CACHE:
            return _MODEL_CACHE[safe_name]

        model = RTDETR(str(get_weight_path(safe_name)))
        _MODEL_CACHE[safe_name] = model
        return model


def current_device_info() -> dict[str, object]:
    cuda_available = torch.cuda.is_available()
    cuda_device_count = torch.cuda.device_count() if cuda_available else 0
    device = "cuda:0" if cuda_available else "cpu"
    for model in _MODEL_CACHE.values():
        inner = getattr(model, "model", None)
        model_device = getattr(inner, "device", None)
        if model_device is not None:
            device = str(model_device)
            break
    return {
        "device": device,
        "torch_cuda_available": cuda_available,
        "cuda_device_count": cuda_device_count,
        "model_cached": bool(_MODEL_CACHE),
    }


def health_info() -> dict:
    available_weights: set[str] = set()
    for root in weight_roots():
        if root.exists():
            available_weights.update(path.name for path in root.glob("*.pt"))

    return {
        "weight_root": str(DEFAULT_WEIGHT_ROOT),
        "fallback_weight_root": str(FALLBACK_WEIGHT_ROOT),
        "available_weights": sorted(available_weights),
        "cached_models": sorted(_MODEL_CACHE.keys()),
        **current_device_info(),
    }
