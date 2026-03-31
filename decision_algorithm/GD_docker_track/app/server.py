import base64

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.inference.engine import set_template, track
from app.model_store import health_info
from app.schemas import TemplateInput, TemplateURLRequest, TrackInput, URLImageRequest
from app.template_store import template_store

app = FastAPI(title="SiamFC Tracking HTTP Service")


def template_output_to_dict(out) -> dict:
    return {
        "status": out.status,
        "cache_version": out.cache_version,
        "initial_bbox_xyxy": out.initial_bbox_xyxy,
        "template_size": out.template_size,
        "cached_template_base64": base64.b64encode(out.cached_template_base64).decode("utf-8"),
        "cached_media_type": out.cached_media_type,
    }


def track_output_to_dict(out) -> dict:
    return {
        "cache_version": out.cache_version,
        "frame_index": out.frame_index,
        "bbox_xyxy": out.bbox_xyxy,
        "score": out.score,
        "tracked_image_base64": base64.b64encode(out.tracked_image_bytes).decode("utf-8"),
        "tracked_media_type": out.tracked_media_type,
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok", "msg": "reload", **health_info(), **template_store.summary()}


@app.get("/ready")
def ready():
    info = health_info()
    available_weights = info.get("available_weights", [])
    cached_models = info.get("cached_models", [])

    if not available_weights:
        raise HTTPException(
            status_code=503,
            detail="No available model weights found in /models directory",
        )

    if not cached_models:
        raise HTTPException(
            status_code=503,
            detail="No models loaded in cache. Data flow not ready",
        )

    return {
        "status": "ready",
        "available_weights": available_weights,
        "cached_models": cached_models,
    }


@app.get("/version")
def version():
    return {"version": "v4"}


@app.post("/template/set/file")
async def set_template_by_file(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")
        out = set_template(
            TemplateInput(image_bytes=image_bytes, initial_bbox_xyxy=[x1, y1, x2, y2]),
            force_replace=False,
        )
        return template_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/template/set/url")
def set_template_by_url(req: TemplateURLRequest):
    try:
        out = set_template(
            TemplateInput(image_url=req.image_url, initial_bbox_xyxy=req.initial_bbox_xyxy),
            force_replace=False,
        )
        return template_output_to_dict(out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/init/file")
async def init_by_file(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
):
    return await set_template_by_file(image=image, x1=x1, y1=y1, x2=x2, y2=y2)


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
):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")
        out = set_template(
            TemplateInput(image_bytes=image_bytes, initial_bbox_xyxy=[x1, y1, x2, y2]),
            force_replace=True,
        )
        return template_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/template/replace/url")
def replace_template_by_url(req: TemplateURLRequest):
    try:
        out = set_template(
            TemplateInput(image_url=req.image_url, initial_bbox_xyxy=req.initial_bbox_xyxy),
            force_replace=True,
        )
        return template_output_to_dict(out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/track/file")
async def track_by_file(image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")
        out = track(TrackInput(image_bytes=image_bytes))
        return track_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/track/url")
def track_by_url(req: URLImageRequest):
    try:
        out = track(TrackInput(image_url=req.image_url))
        return track_output_to_dict(out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
