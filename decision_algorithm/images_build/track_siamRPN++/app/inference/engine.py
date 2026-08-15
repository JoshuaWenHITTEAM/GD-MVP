from __future__ import annotations

from app.inference.io_utils import annotate_bbox, encode_rgb_to_jpeg_bytes, load_image_to_rgb
from app.model_store import get_model
from app.schemas import TemplateInput, TemplateOutput, TrackInput, TrackOutput
from app.template_store import template_store


def set_template(req: TemplateInput, force_replace: bool) -> TemplateOutput:
    model = get_model()
    image_rgb = load_image_to_rgb(req)
    prepared = model.prepare_template(image_rgb, req.initial_bbox_xyxy)
    cached = template_store.set(
        template_rgb=prepared.template_rgb,
        bbox_xyxy=prepared.template_bbox_xyxy,
        force_replace=force_replace,
    )
    preview_bytes = encode_rgb_to_jpeg_bytes(cached.template_rgb) if req.return_image else None
    preview_media_type = "image/jpeg" if req.return_image else None
    return TemplateOutput(
        status="replaced" if force_replace and cached.cache_version > 1 else "created",
        cache_version=cached.cache_version,
        initial_bbox_xyxy=list(cached.template_bbox_xyxy),
        template_size=prepared.template_size,
        cached_template_base64=preview_bytes,
        cached_media_type=preview_media_type,
    )


def track(req: TrackInput) -> TrackOutput:
    model = get_model()
    template_store.get()
    image_rgb = load_image_to_rgb(req)
    tracked = model.track(image_rgb)
    updated = template_store.update_tracking_state(
        bbox_xyxy=tracked.bbox_xyxy,
        score=tracked.score,
    )
    tracked_bytes = None
    tracked_media_type = None
    if req.return_image:
        tracked_rgb = annotate_bbox(image_rgb, tracked.bbox_xyxy)
        tracked_bytes = encode_rgb_to_jpeg_bytes(tracked_rgb)
        tracked_media_type = "image/jpeg"
    return TrackOutput(
        cache_version=updated.cache_version,
        frame_index=updated.frame_index,
        bbox_xyxy=tracked.bbox_xyxy,
        score=tracked.score,
        tracked_image_bytes=tracked_bytes,
        tracked_media_type=tracked_media_type,
    )
