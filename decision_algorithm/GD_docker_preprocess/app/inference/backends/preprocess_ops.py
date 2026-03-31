import numpy as np
import torch
import torchvision.transforms as tfs

from app.inference.backends.basic_ops import (
    gamma_correction,
    multi_scale_retinex,
    unsharp_mask,
    wavelet_denoise,
)


def apply_preprocess(method_name: str, image_rgb: np.ndarray, model=None) -> np.ndarray:
    if method_name == "none":
        return image_rgb
    if method_name == "denoise":
        return wavelet_denoise(image_rgb)
    if method_name == "gamma":
        return gamma_correction(image_rgb)
    if method_name == "retinex":
        return multi_scale_retinex(image_rgb)
    if method_name == "usm":
        return unsharp_mask(image_rgb)
    if method_name == "dehaze":
        if model is None:
            raise ValueError("dehaze requires a loaded model")
        return run_dehaze(model, image_rgb)
    raise ValueError(f"unsupported method_name='{method_name}'")


def run_dehaze(model, image_rgb: np.ndarray) -> np.ndarray:
    device = next(model.parameters()).device
    haze_tensor = tfs.ToTensor()(image_rgb)[None, ::].to(device)
    with torch.no_grad():
        pred = model(haze_tensor)
    output = torch.squeeze(pred.clamp(0, 1).cpu()).permute(1, 2, 0).numpy()
    return np.clip(output * 255.0, 0, 255).astype(np.uint8)

