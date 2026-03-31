from pathlib import Path
from threading import Lock
from ultralytics import YOLO

WEIGHT_ROOT = Path("/models")

_MODEL_CACHE: dict[str, YOLO] = {}
_MODEL_LOCK = Lock()


def get_weight_path(model_name: str) -> Path:
    if not model_name or not model_name.strip():
        raise ValueError("model_name is empty")

    safe_name = model_name.strip()
    weight_path = WEIGHT_ROOT / f"{safe_name}.pt"

    if not weight_path.exists():
        raise ValueError(
            f"weight file not found for model_name='{safe_name}', expected path='{weight_path}'"
        )
    return weight_path


def get_model(model_name: str) -> YOLO:
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    with _MODEL_LOCK:
        if model_name in _MODEL_CACHE:
            return _MODEL_CACHE[model_name]

        weight_path = get_weight_path(model_name)
        model = YOLO(str(weight_path))
        _MODEL_CACHE[model_name] = model
        return model


def health_info():
    available_weights = sorted([p.name for p in WEIGHT_ROOT.glob("*.pt")]) if WEIGHT_ROOT.exists() else []
    cached_models = sorted(list(_MODEL_CACHE.keys()))
    return {
        "weight_root": str(WEIGHT_ROOT),
        "available_weights": available_weights,
        "cached_models": cached_models,
    }