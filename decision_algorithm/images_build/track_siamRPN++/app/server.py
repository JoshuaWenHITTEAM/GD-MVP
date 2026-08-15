from __future__ import annotations

import base64

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
import numpy as np

from app.inference.engine import set_template, track
from app.model_store import health_info
from app.schemas import TemplateInput, TemplateURLRequest, TrackInput, URLImageRequest
from app.template_store import template_store

app = FastAPI(title="SiamRPN++ Tracking HTTP Service")


def _raw_bytes_to_image_array(image_bytes: bytes, width: int, height: int, channels: int) -> np.ndarray:
    if not image_bytes:
        raise HTTPException(status_code=400, detail="empty raw image body")
    if width <= 0 or height <= 0 or channels not in (1, 3):
        raise HTTPException(status_code=400, detail="raw image must have positive width/height and 1 or 3 channels")
    expected_size = width * height * channels
    if len(image_bytes) != expected_size:
        raise HTTPException(
            status_code=400,
            detail=f"raw image size mismatch: got {len(image_bytes)}, expected {expected_size}",
        )
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    if channels == 1:
        return image_array.reshape((height, width))
    return image_array.reshape((height, width, channels))


def template_output_to_dict(out) -> dict:
    payload = {
        "status": out.status,
        "cache_version": out.cache_version,
        "initial_bbox_xyxy": out.initial_bbox_xyxy,
        "template_size": out.template_size,
    }
    if out.cached_template_base64 is not None:
        payload["cached_template_base64"] = base64.b64encode(out.cached_template_base64).decode("utf-8")
        payload["cached_media_type"] = out.cached_media_type
    return payload


def track_output_to_dict(out) -> dict:
    payload = {
        "cache_version": out.cache_version,
        "frame_index": out.frame_index,
        "bbox_xyxy": out.bbox_xyxy,
        "score": out.score,
    }
    if out.tracked_image_bytes is not None:
        payload["tracked_image_base64"] = base64.b64encode(out.tracked_image_bytes).decode("utf-8")
        payload["tracked_media_type"] = out.tracked_media_type
    return payload


@app.get("/healthz")
def healthz():
    return {"status": "ok", "msg": "reload", **health_info(), **template_store.summary()}


@app.get("/ready")
def ready():
    info = health_info()
    available_weights = info.get("available_weights", [])
    cached_models = info.get("cached_models", [])
    if not available_weights:
        raise HTTPException(status_code=503, detail="No available model weights found in configured model directories")
    if not cached_models:
        raise HTTPException(status_code=503, detail="No models loaded in cache. Data flow not ready")
    return {"status": "ready", "available_weights": available_weights, "cached_models": cached_models}


@app.get("/version")
def version():
    return {"version": "track-siamrpnpp-http-v1"}


@app.post("/template/reset")
def reset_template():
    return template_store.reset()


@app.post("/template/set/file")
async def set_template_by_file(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
    return_image: bool = Form(True),
):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")
        out = set_template(
            TemplateInput(
                image_bytes=image_bytes,
                initial_bbox_xyxy=[x1, y1, x2, y2],
                return_image=return_image,
            ),
            force_replace=False,
        )
        return template_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/template/set/url")
def set_template_by_url(req: TemplateURLRequest):
    try:
        out = set_template(
            TemplateInput(
                image_url=req.image_url,
                initial_bbox_xyxy=req.initial_bbox_xyxy,
                return_image=req.return_image,
            ),
            force_replace=False,
        )
        return template_output_to_dict(out)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/init/file")
async def init_by_file(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
    return_image: bool = Form(True),
):
    return await set_template_by_file(
        image=image,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        return_image=return_image,
    )


@app.post("/init/url")
def init_by_url(req: TemplateURLRequest):
    return set_template_by_url(req)


@app.post("/template/replace/file")
async def replace_template_by_file(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
    return_image: bool = Form(True),
):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")
        out = set_template(
            TemplateInput(
                image_bytes=image_bytes,
                initial_bbox_xyxy=[x1, y1, x2, y2],
                return_image=return_image,
            ),
            force_replace=True,
        )
        return template_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/template/replace/url")
def replace_template_by_url(req: TemplateURLRequest):
    try:
        out = set_template(
            TemplateInput(
                image_url=req.image_url,
                initial_bbox_xyxy=req.initial_bbox_xyxy,
                return_image=req.return_image,
            ),
            force_replace=True,
        )
        return template_output_to_dict(out)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


async def _set_template_by_raw_body(
    request: Request,
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    width: int,
    height: int,
    channels: int,
    return_image: bool,
    force_replace: bool,
):
    try:
        image_bytes = await request.body()
        image_array = _raw_bytes_to_image_array(image_bytes, width, height, channels)
        out = set_template(
            TemplateInput(
                image_array=image_array,
                initial_bbox_xyxy=[x1, y1, x2, y2],
                return_image=return_image,
            ),
            force_replace=force_replace,
        )
        return template_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/template/set/raw-body")
async def set_template_by_raw_body(
    request: Request,
    x1: int = Query(...),
    y1: int = Query(...),
    x2: int = Query(...),
    y2: int = Query(...),
    width: int = Query(...),
    height: int = Query(...),
    channels: int = Query(1),
    return_image: bool = Query(True),
):
    return await _set_template_by_raw_body(
        request,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        width=width,
        height=height,
        channels=channels,
        return_image=return_image,
        force_replace=False,
    )


@app.post("/init/raw-body")
async def init_by_raw_body(
    request: Request,
    x1: int = Query(...),
    y1: int = Query(...),
    x2: int = Query(...),
    y2: int = Query(...),
    width: int = Query(...),
    height: int = Query(...),
    channels: int = Query(1),
    return_image: bool = Query(True),
):
    return await set_template_by_raw_body(
        request,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        width=width,
        height=height,
        channels=channels,
        return_image=return_image,
    )


@app.post("/template/replace/raw-body")
async def replace_template_by_raw_body(
    request: Request,
    x1: int = Query(...),
    y1: int = Query(...),
    x2: int = Query(...),
    y2: int = Query(...),
    width: int = Query(...),
    height: int = Query(...),
    channels: int = Query(1),
    return_image: bool = Query(True),
):
    return await _set_template_by_raw_body(
        request,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        width=width,
        height=height,
        channels=channels,
        return_image=return_image,
        force_replace=True,
    )


@app.post("/track/file")
async def track_by_file(image: UploadFile = File(...), return_image: bool = Form(True)):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")
        out = track(TrackInput(image_bytes=image_bytes, return_image=return_image))
        return track_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/track/raw-body")
async def track_by_raw_body(
    request: Request,
    width: int = Query(...),
    height: int = Query(...),
    channels: int = Query(1),
    return_image: bool = Query(True),
):
    try:
        image_bytes = await request.body()
        image_array = _raw_bytes_to_image_array(image_bytes, width, height, channels)
        out = track(TrackInput(image_array=image_array, return_image=return_image))
        return track_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/track/url")
def track_by_url(req: URLImageRequest):
    try:
        out = track(TrackInput(image_url=req.image_url, return_image=req.return_image))
        return track_output_to_dict(out)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
