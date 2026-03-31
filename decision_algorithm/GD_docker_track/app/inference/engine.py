import cv2
import numpy as np
import torch

from app.inference.io_utils import annotate_bbox, encode_rgb_to_jpeg_bytes, load_image_to_rgb
from app.model_store import get_model
from app.schemas import TemplateInput, TemplateOutput, TrackInput, TrackOutput
from app.template_store import (
    EXEMPLAR_SIZE,
    INSTANCE_SIZE,
    crop_and_resize,
    normalize_bbox_xyxy,
    template_store,
    to_tensor,
)

SCALE_FACTORS = np.array([0.97, 1.0, 1.03], dtype=np.float32)
SCALE_PENALTY = 0.9745
SCALE_LR = 0.59
RESPONSE_UP = 16
WINDOW_INFLUENCE = 0.176


def set_template(req: TemplateInput, force_replace: bool) -> TemplateOutput:
    model = get_model()
    image_rgb = load_image_to_rgb(req)
    bbox_xyxy = normalize_bbox_xyxy(req.initial_bbox_xyxy, image_rgb.shape[:2])
    cached = template_store.set(image_rgb, bbox_xyxy, model, force_replace=force_replace)
    preview_bytes = encode_rgb_to_jpeg_bytes(cached.template_rgb)
    return TemplateOutput(
        status="replaced" if force_replace and cached.cache_version > 1 else "created",
        cache_version=cached.cache_version,
        initial_bbox_xyxy=list(cached.template_bbox_xyxy),
        template_size=[int(round(cached.target_size[0])), int(round(cached.target_size[1]))],
        cached_template_base64=preview_bytes,
        cached_media_type="image/jpeg",
    )


def track(req: TrackInput) -> TrackOutput:
    model = get_model()
    cached = template_store.get()
    image_rgb = load_image_to_rgb(req)

    device = next(model.parameters()).device
    scale_x_sizes = cached.x_size * SCALE_FACTORS
    response_maps = []
    raw_scores = []

    with torch.no_grad():
        for scale_x_size in scale_x_sizes:
            search_rgb = crop_and_resize(
                image_rgb,
                cached.center_pos,
                float(scale_x_size),
                INSTANCE_SIZE,
                cached.channel_average,
            )
            search_tensor = to_tensor(search_rgb, device)
            search_feat = model.feature(search_tensor)
            response = model.correlate(cached.exemplar_feat, search_feat).squeeze().detach().cpu().numpy()
            response = ensure_2d_response(response)
            response = cv2.resize(
                response,
                (response.shape[1] * RESPONSE_UP, response.shape[0] * RESPONSE_UP),
                interpolation=cv2.INTER_CUBIC,
            )
            response_maps.append(response)
            raw_scores.append(float(response.max()))

    penalized_scores = np.array(raw_scores, dtype=np.float32)
    penalized_scores[[0, 2]] *= SCALE_PENALTY
    best_scale_idx = int(np.argmax(penalized_scores))
    best_scale = float(SCALE_FACTORS[best_scale_idx])
    response = response_maps[best_scale_idx]

    response -= response.min()
    if response.sum() > 0:
        response /= response.sum()
    response = (1 - WINDOW_INFLUENCE) * response + WINDOW_INFLUENCE * cosine_window(response.shape)

    peak_pos = np.array(np.unravel_index(np.argmax(response), response.shape), dtype=np.float32)
    response_center = (np.array(response.shape, dtype=np.float32) - 1.0) / 2.0
    disp_in_response = peak_pos - response_center
    disp_in_instance = disp_in_response[::-1] * model.total_stride / RESPONSE_UP
    disp_in_image = disp_in_instance * (scale_x_sizes[best_scale_idx] / INSTANCE_SIZE)

    new_center_pos = cached.center_pos + disp_in_image.astype(np.float32)
    scale_ratio = (1 - SCALE_LR) + SCALE_LR * best_scale
    new_target_size = cached.target_size * scale_ratio
    new_z_size = cached.z_size * scale_ratio
    new_x_size = cached.x_size * scale_ratio

    bbox_xyxy = center_size_to_bbox_xyxy(new_center_pos, new_target_size, image_rgb.shape[:2])
    updated = template_store.update_tracking_state(
        center_pos=new_center_pos,
        target_size=new_target_size,
        z_size=float(new_z_size),
        x_size=float(new_x_size),
        bbox_xyxy=bbox_xyxy,
        score=float(raw_scores[best_scale_idx]),
    )

    tracked_rgb = annotate_bbox(image_rgb, bbox_xyxy)
    tracked_bytes = encode_rgb_to_jpeg_bytes(tracked_rgb)
    return TrackOutput(
        cache_version=updated.cache_version,
        frame_index=updated.frame_index,
        bbox_xyxy=bbox_xyxy,
        score=float(raw_scores[best_scale_idx]),
        tracked_image_bytes=tracked_bytes,
        tracked_media_type="image/jpeg",
    )


def ensure_2d_response(response: np.ndarray) -> np.ndarray:
    response = np.asarray(response)
    while response.ndim > 2:
        response = response.squeeze(0)
    if response.ndim != 2:
        raise ValueError(f"unexpected response shape: {response.shape}")
    return response


def cosine_window(shape) -> np.ndarray:
    h, w = shape
    return np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)


def center_size_to_bbox_xyxy(center_pos: np.ndarray, target_size: np.ndarray, image_shape) -> list[int]:
    h, w = image_shape
    half_w = max(1.0, float(target_size[0]) / 2.0)
    half_h = max(1.0, float(target_size[1]) / 2.0)
    x1 = int(round(max(0, center_pos[0] - half_w)))
    y1 = int(round(max(0, center_pos[1] - half_h)))
    x2 = int(round(min(w - 1, center_pos[0] + half_w)))
    y2 = int(round(min(h - 1, center_pos[1] + half_h)))
    if x2 <= x1:
        x2 = min(w - 1, x1 + 1)
    if y2 <= y1:
        y2 = min(h - 1, y1 + 1)
    return [x1, y1, x2, y2]
