from pathlib import Path
from threading import Lock

import torch

from app.inference.backends.c2pnet_model import C2PNet

WEIGHT_ROOT = Path("/models")
WEIGHTED_METHODS = {"dehaze"}
AVAILABLE_METHODS = ("none", "denoise", "gamma", "retinex", "usm", "dehaze")

_MODEL_CACHE: dict[str, torch.nn.Module] = {}
_MODEL_LOCK = Lock()


def normalize_method_name(method_name: str) -> str:
    if not method_name or not method_name.strip():
        raise ValueError("method_name is empty")

    safe_name = method_name.strip()
    if safe_name not in AVAILABLE_METHODS:
        raise ValueError(f"unsupported method_name='{safe_name}'")
    return safe_name


def get_weight_path(method_name: str) -> Path:
    safe_name = normalize_method_name(method_name)
    if safe_name not in WEIGHTED_METHODS:
        raise ValueError(f"method_name='{safe_name}' does not require a weight file")

    weight_path = WEIGHT_ROOT / f"{safe_name.capitalize()}.pkl"
    if not weight_path.exists():
        raise ValueError(
            f"weight file not found for method_name='{safe_name}', expected path='{weight_path}'"
        )
    return weight_path


def load_dehaze_model(weight_path: Path) -> torch.nn.Module:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(str(weight_path), map_location=device)

    model = C2PNet(gps=3, blocks=19)
    model.load_state_dict(checkpoint["model"])
    model = model.to(device)
    model.eval()
    return model


def get_weighted_model(method_name: str):
    safe_name = normalize_method_name(method_name)
    if safe_name not in WEIGHTED_METHODS:
        return None

    if safe_name in _MODEL_CACHE:
        return _MODEL_CACHE[safe_name]

    with _MODEL_LOCK:
        if safe_name in _MODEL_CACHE:
            return _MODEL_CACHE[safe_name]

        weight_path = get_weight_path(safe_name)
        model = load_dehaze_model(weight_path)
        _MODEL_CACHE[safe_name] = model
        return model


def health_info():
    available_weights = sorted([p.name for p in WEIGHT_ROOT.glob("*.pkl")]) if WEIGHT_ROOT.exists() else []
    cached_models = sorted(list(_MODEL_CACHE.keys()))
    return {
        "weight_root": str(WEIGHT_ROOT),
        "available_methods": list(AVAILABLE_METHODS),
        "weighted_methods": sorted(list(WEIGHTED_METHODS)),
        "available_weights": available_weights,
        "cached_models": cached_models,
    }

