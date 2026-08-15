from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import os
from pathlib import Path
import time
from typing import Any

import cv2 as cv
import numpy as np
import torch

from app.inference.sample_target import sample_target
from lib.config.avtrack.config import cfg as base_cfg
from lib.config.avtrack.config import update_config_from_file
from lib.models.avtrack import build_avtrack
from lib.train.admin.stats import AverageMeter, StatValue
from lib.utils.box_ops import clip_box


def _positive_int_env(name: str) -> int | None:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        return None
    return value if value > 0 else None


def configure_runtime_threads() -> None:
    opencv_threads = _positive_int_env("OPENCV_NUM_THREADS")
    if opencv_threads is not None:
        cv.setNumThreads(opencv_threads)

    torch_threads = _positive_int_env("TORCH_NUM_THREADS")
    if torch_threads is not None:
        torch.set_num_threads(torch_threads)


class NestedTensor:
    def __init__(self, tensors: torch.Tensor, mask: torch.Tensor):
        self.tensors = tensors
        self.mask = mask

    def to(self, device):
        return NestedTensor(self.tensors.to(device), self.mask.to(device) if self.mask is not None else None)


class ImagePreprocessor:
    def __init__(self, device: torch.device):
        self.device = device
        self.mean = torch.tensor([0.485, 0.456, 0.406], device=device).view((1, 3, 1, 1))
        self.std = torch.tensor([0.229, 0.224, 0.225], device=device).view((1, 3, 1, 1))

    def process(self, img_arr: np.ndarray, amask_arr: np.ndarray) -> NestedTensor:
        img_tensor = torch.as_tensor(img_arr, device=self.device).float()
        if img_tensor.ndim == 2:
            img_tensor = img_tensor.unsqueeze(0).unsqueeze(0).expand(-1, 3, -1, -1)
        elif img_tensor.ndim == 3 and img_tensor.shape[2] == 1:
            img_tensor = img_tensor.permute((2, 0, 1)).unsqueeze(dim=0).expand(-1, 3, -1, -1)
        elif img_tensor.ndim == 3 and img_tensor.shape[2] == 3:
            img_tensor = img_tensor.permute((2, 0, 1)).unsqueeze(dim=0)
        else:
            raise ValueError(f"expected HW grayscale or HWC image, got shape={tuple(img_tensor.shape)}")
        img_tensor_norm = ((img_tensor / 255.0) - self.mean) / self.std
        amask_tensor = torch.from_numpy(amask_arr).to(torch.bool).to(self.device).unsqueeze(dim=0)
        return NestedTensor(img_tensor_norm, amask_tensor)


def hann1d(sz: int, centered: bool = True) -> torch.Tensor:
    if centered:
        return 0.5 * (1 - torch.cos((2 * math.pi / (sz + 1)) * torch.arange(1, sz + 1).float()))
    w = 0.5 * (1 + torch.cos((2 * math.pi / (sz + 2)) * torch.arange(0, sz // 2 + 1).float()))
    return torch.cat([w, w[1 : sz - sz // 2].flip((0,))])


def hann2d(sz: torch.Tensor, centered: bool = True) -> torch.Tensor:
    return hann1d(sz[0].item(), centered).reshape(1, 1, -1, 1) * hann1d(sz[1].item(), centered).reshape(1, 1, 1, -1)


@dataclass
class PreparedTemplate:
    template_rgb: np.ndarray
    template_bbox_xyxy: list[int]
    initial_state_xywh: list[float]
    template_size: list[int]
    z_dict1: Any


@dataclass
class TrackStep:
    state_xywh: list[float]
    bbox_xyxy: list[int]
    score: float
    timings_ms: dict[str, float]


class AVTrackRuntime:
    def __init__(self, config_path: Path, weight_path: Path, device: torch.device):
        configure_runtime_threads()
        self.config_path = config_path
        self.weight_path = weight_path
        self.device = device
        self.cfg = deepcopy(base_cfg)
        update_config_from_file(str(config_path), self.cfg)

        network = build_avtrack(self.cfg, training=False)
        checkpoint = self._load_checkpoint(weight_path, device)
        network.load_state_dict(checkpoint["net"], strict=True)
        self.network = network.to(device)
        self.network.eval()

        self.preprocessor = ImagePreprocessor(device)
        self.template_factor = float(self.cfg.TEST.TEMPLATE_FACTOR)
        self.template_size = int(self.cfg.TEST.TEMPLATE_SIZE)
        self.search_factor = float(self.cfg.TEST.SEARCH_FACTOR)
        self.search_size = int(self.cfg.TEST.SEARCH_SIZE)
        self.feat_sz = self.search_size // int(self.cfg.MODEL.BACKBONE.STRIDE)
        self.output_window = hann2d(torch.tensor([self.feat_sz, self.feat_sz]).long(), centered=True).to(device)
        self.is_distill = bool(self.cfg.MODEL["IS_DISTILL"])

    def _load_checkpoint(self, weight_path: Path, device: torch.device) -> dict[str, Any]:
        load_kwargs = {"map_location": device}
        try:
            torch.serialization.add_safe_globals([AverageMeter, StatValue])
        except AttributeError:
            pass
        try:
            checkpoint = torch.load(str(weight_path), weights_only=True, **load_kwargs)
        except TypeError:
            checkpoint = torch.load(str(weight_path), **load_kwargs)
        except Exception as exc:
            if "Weights only load failed" not in str(exc):
                raise
            checkpoint = torch.load(str(weight_path), weights_only=False, **load_kwargs)

        if not isinstance(checkpoint, dict) or "net" not in checkpoint:
            raise ValueError(f"unexpected checkpoint format: {weight_path}")
        return checkpoint

    def _sync_if_cuda(self) -> None:
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)

    def _xyxy_to_xywh(self, bbox_xyxy: list[int]) -> list[float]:
        x1, y1, x2, y2 = [float(v) for v in bbox_xyxy]
        return [x1, y1, max(1.0, x2 - x1), max(1.0, y2 - y1)]

    def _xywh_to_xyxy(self, bbox_xywh: list[float], image_shape) -> list[int]:
        x, y, w, h = bbox_xywh
        h_img, w_img = image_shape
        x1 = int(round(max(0.0, min(w_img - 1.0, x))))
        y1 = int(round(max(0.0, min(h_img - 1.0, y))))
        x2 = int(round(max(0.0, min(w_img - 1.0, x + w))))
        y2 = int(round(max(0.0, min(h_img - 1.0, y + h))))
        if x2 <= x1:
            x2 = min(w_img - 1, x1 + 1)
        if y2 <= y1:
            y2 = min(h_img - 1, y1 + 1)
        return [x1, y1, x2, y2]

    def prepare_template(self, image_rgb: np.ndarray, bbox_xyxy: list[int]) -> PreparedTemplate:
        init_bbox = self._xyxy_to_xywh(bbox_xyxy)
        z_patch_arr, _, z_amask_arr = sample_target(
            image_rgb,
            init_bbox,
            self.template_factor,
            output_sz=self.template_size,
        )
        template = self.preprocessor.process(z_patch_arr, z_amask_arr)
        with torch.no_grad():
            z_dict1 = template

        return PreparedTemplate(
            template_rgb=z_patch_arr,
            template_bbox_xyxy=bbox_xyxy,
            initial_state_xywh=init_bbox,
            template_size=[int(round(init_bbox[2])), int(round(init_bbox[3]))],
            z_dict1=z_dict1,
        )

    def track(self, image_rgb: np.ndarray, z_dict1: Any, state_xywh: list[float]) -> TrackStep:
        algorithm_started_at = time.perf_counter()
        image_h, image_w = image_rgb.shape[:2]
        crop_started_at = time.perf_counter()
        x_patch_arr, resize_factor, x_amask_arr = sample_target(
            image_rgb,
            state_xywh,
            self.search_factor,
            output_sz=self.search_size,
        )
        crop_ms = (time.perf_counter() - crop_started_at) * 1000.0
        preprocess_started_at = time.perf_counter()
        search = self.preprocessor.process(x_patch_arr, x_amask_arr)
        self._sync_if_cuda()
        preprocess_ms = (time.perf_counter() - preprocess_started_at) * 1000.0

        self._sync_if_cuda()
        forward_started_at = time.perf_counter()
        with torch.no_grad():
            out_dict = self.network.forward(
                template=z_dict1.tensors,
                search=search.tensors,
                template_anno=[],
                search_anno=[],
                is_distill=self.is_distill,
            )
        self._sync_if_cuda()
        forward_ms = (time.perf_counter() - forward_started_at) * 1000.0

        postprocess_started_at = time.perf_counter()
        pred_score_map = out_dict["score_map"]
        response = self.output_window * pred_score_map
        pred_boxes, max_score = self.network.box_head.cal_bbox(
            response,
            out_dict["size_map"],
            out_dict["offset_map"],
            return_score=True,
        )
        pred_boxes = pred_boxes.view(-1, 4)
        pred_box = (pred_boxes.mean(dim=0) * self.search_size / resize_factor).tolist()
        new_state = clip_box(self._map_box_back(pred_box, resize_factor, state_xywh), image_h, image_w, margin=10)
        bbox_xyxy = self._xywh_to_xyxy(new_state, image_rgb.shape[:2])
        self._sync_if_cuda()
        postprocess_ms = (time.perf_counter() - postprocess_started_at) * 1000.0
        algorithm_total_ms = (time.perf_counter() - algorithm_started_at) * 1000.0
        return TrackStep(
            state_xywh=[float(v) for v in new_state],
            bbox_xyxy=bbox_xyxy,
            score=float(max_score.view(-1)[0].item()),
            timings_ms={
                "track_algorithm_total_ms": round(algorithm_total_ms, 3),
                "track_search_crop_ms": round(crop_ms, 3),
                "track_tensor_preprocess_ms": round(preprocess_ms, 3),
                "track_model_forward_ms": round(forward_ms, 3),
                "track_postprocess_ms": round(postprocess_ms, 3),
            },
        )

    def _map_box_back(self, pred_box: list[float], resize_factor: float, prev_state: list[float]) -> list[float]:
        cx_prev = prev_state[0] + 0.5 * prev_state[2]
        cy_prev = prev_state[1] + 0.5 * prev_state[3]
        cx, cy, w, h = pred_box
        half_side = 0.5 * self.search_size / resize_factor
        cx_real = cx + (cx_prev - half_side)
        cy_real = cy + (cy_prev - half_side)
        return [cx_real - 0.5 * w, cy_real - 0.5 * h, w, h]
