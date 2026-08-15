import os
import time

from app.inference.io_utils import annotate_bbox, encode_rgb_to_jpeg_bytes, load_image_to_rgb
from app.model_store import get_model
from app.schemas import TemplateInput, TemplateOutput, TrackInput, TrackOutput
from app.template_store import template_store


MIN_TRACK_SCORE = float(os.getenv("TRACK_ADVI_MIN_SCORE", "0.55"))


def set_template(req: TemplateInput, force_replace: bool) -> TemplateOutput:
    model = get_model()
    image_rgb = load_image_to_rgb(req)
    prepared = model.prepare_template(image_rgb, req.initial_bbox_xyxy)
    cached = template_store.set(
        template_rgb=prepared.template_rgb,
        z_dict1=prepared.z_dict1,
        bbox_xyxy=prepared.template_bbox_xyxy,
        state_xywh=prepared.initial_state_xywh,
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
    engine_started_at = time.perf_counter()
    model_started_at = time.perf_counter()
    model = get_model()
    model_get_ms = (time.perf_counter() - model_started_at) * 1000.0
    template_started_at = time.perf_counter()
    cached = template_store.get()
    template_get_ms = (time.perf_counter() - template_started_at) * 1000.0
    decode_started_at = time.perf_counter()
    image_rgb = load_image_to_rgb(req)
    decode_ms = (time.perf_counter() - decode_started_at) * 1000.0
    tracked = model.track(image_rgb, cached.z_dict1, cached.state_xywh)
    state_started_at = time.perf_counter()
    accepted = tracked.score >= MIN_TRACK_SCORE
    if accepted:
        updated = template_store.update_tracking_state(
            state_xywh=tracked.state_xywh,
            bbox_xyxy=tracked.bbox_xyxy,
            score=tracked.score,
        )
        bbox_xyxy = tracked.bbox_xyxy
    else:
        updated = template_store.reject_tracking_state(score=tracked.score)
        bbox_xyxy = list(cached.current_bbox_xyxy)
    state_update_ms = (time.perf_counter() - state_started_at) * 1000.0
    tracked_bytes = None
    tracked_media_type = None
    render_encode_ms = 0.0
    if req.return_image:
        render_started_at = time.perf_counter()
        tracked_rgb = annotate_bbox(image_rgb, bbox_xyxy)
        tracked_bytes = encode_rgb_to_jpeg_bytes(tracked_rgb)
        tracked_media_type = "image/jpeg"
        render_encode_ms = (time.perf_counter() - render_started_at) * 1000.0
    engine_total_ms = (time.perf_counter() - engine_started_at) * 1000.0
    timings_ms = {
        "track_engine_total_ms": round(engine_total_ms, 3),
        "track_model_get_ms": round(model_get_ms, 3),
        "track_template_get_ms": round(template_get_ms, 3),
        "track_decode_ms": round(decode_ms, 3),
        "track_state_update_ms": round(state_update_ms, 3),
        "track_render_encode_ms": round(render_encode_ms, 3),
        "track_min_score": round(MIN_TRACK_SCORE, 3),
        "track_score_accepted": accepted,
    }
    timings_ms.update(tracked.timings_ms)
    return TrackOutput(
        cache_version=updated.cache_version,
        frame_index=updated.frame_index,
        bbox_xyxy=bbox_xyxy,
        score=tracked.score,
        tracked_image_bytes=tracked_bytes,
        tracked_media_type=tracked_media_type,
        timings_ms=timings_ms,
    )
