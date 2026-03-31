from pathlib import Path
from threading import Lock
from typing import Optional

import torch

from app.inference.backends.siamfc_model import SiamFCNet

WEIGHT_ROOT = Path("/models")
DEFAULT_WEIGHT_NAME = "siamfc_alexnet_e50.pth"

_MODEL_CACHE: Optional[SiamFCNet] = None
_MODEL_LOCK = Lock()


def get_weight_path() -> Path:
    weight_path = WEIGHT_ROOT / DEFAULT_WEIGHT_NAME
    if not weight_path.exists():
        raise ValueError(f"weight file not found, expected path='{weight_path}'")
    return weight_path


def load_model() -> SiamFCNet:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    weight_path = get_weight_path()

    checkpoint = torch.load(str(weight_path), map_location=device)
    state_dict = checkpoint.get("state_dict", checkpoint)
    cleaned_state_dict = {}
    for key, value in state_dict.items():
        if key.startswith("module."):
            key = key[7:]
        if key.startswith("backbone.features.") or key.startswith("backbone."):
            cleaned_state_dict[key] = value
        else:
            cleaned_state_dict[key] = value

    model = SiamFCNet()
    model.load_state_dict(cleaned_state_dict, strict=False)
    model = model.to(device)
    model.eval()
    return model


def get_model() -> SiamFCNet:
    global _MODEL_CACHE

    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    with _MODEL_LOCK:
        if _MODEL_CACHE is not None:
            return _MODEL_CACHE
        _MODEL_CACHE = load_model()
        return _MODEL_CACHE


def health_info():
    available_weights = sorted([p.name for p in WEIGHT_ROOT.glob("*.pth")]) if WEIGHT_ROOT.exists() else []
    cached_models = [DEFAULT_WEIGHT_NAME] if _MODEL_CACHE is not None else []
    return {
        "weight_root": str(WEIGHT_ROOT),
        "default_weight_name": DEFAULT_WEIGHT_NAME,
        "available_weights": available_weights,
        "model_cached": _MODEL_CACHE is not None,
        "cached_models": cached_models,
    }
