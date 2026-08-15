import base64
import time

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
import numpy as np

from app.inference.engine import run_infer
from app.model_store import health_info
from app.schemas import InferInput, URLInferRequest

app = FastAPI(title="AntiUAV YOLO HTTP Inference Service")


def infer_output_to_dict(out, timings_ms: dict | None = None) -> dict:
    payload = {
        "model_name": out.model_name,
        "num_detections": out.num_detections,
        "detections": out.detections,
    }
    if timings_ms:
        payload["timings_ms"] = dict(timings_ms)
    if out.yolo_txt is not None:
        payload["yolo_txt"] = out.yolo_txt
    if out.annotated_image_bytes is not None:
        payload["annotated_image_base64"] = base64.b64encode(out.annotated_image_bytes).decode("utf-8")
        payload["annotated_media_type"] = out.annotated_media_type
    return payload


@app.get("/healthz")
def healthz():
    return {"status": "ok", "msg": "reload", **health_info()}


@app.get("/ready")
def ready():
    info = health_info()
    available_weights = info.get("available_weights", [])
    cached_models = info.get("cached_models", [])

    if not available_weights:
        raise HTTPException(
            status_code=503,
            detail="No available model weights found in configured model directories",
        )

    if not cached_models:
        raise HTTPException(
            status_code=503,
            detail="No models loaded in cache. Run one inference request first or preload models.",
        )

    return {
        "status": "ready",
        "available_weights": available_weights,
        "cached_models": cached_models,
    }


@app.get("/version")
def version():
    return {"version": "det-yolo-http-v1"}


@app.post("/infer/url")
def infer_by_url(req: URLInferRequest):
    try:
        out = run_infer(
            InferInput(
                model_name=req.model_name,
                image_url=req.image_url,
                return_image=req.return_image,
                return_yolo_txt=req.return_yolo_txt,
            )
        )
        return infer_output_to_dict(out)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/infer/file")
async def infer_by_file(
    model_name: str = Form(...),
    image: UploadFile = File(...),
    return_image: bool = Form(True),
    return_yolo_txt: bool = Form(True),
):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")

        out = run_infer(
            InferInput(
                model_name=model_name,
                image_bytes=image_bytes,
                return_image=return_image,
                return_yolo_txt=return_yolo_txt,
            )
        )
        return infer_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/infer/raw-body")
async def infer_by_raw_body(
    request: Request,
    model_name: str = Query(...),
    width: int = Query(...),
    height: int = Query(...),
    channels: int = Query(1),
    return_image: bool = Query(True),
    return_yolo_txt: bool = Query(True),
):
    handler_started_at = time.perf_counter()
    try:
        read_started_at = time.perf_counter()
        image_bytes = await request.body()
        upload_read_ms = (time.perf_counter() - read_started_at) * 1000.0
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

        decode_started_at = time.perf_counter()
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        if channels == 1:
            image_array = image_array.reshape((height, width))
        else:
            image_array = image_array.reshape((height, width, channels))
        raw_decode_ms = (time.perf_counter() - decode_started_at) * 1000.0
        infer_started_at = time.perf_counter()
        out = run_infer(
            InferInput(
                model_name=model_name,
                image_array=image_array,
                return_image=return_image,
                return_yolo_txt=return_yolo_txt,
            )
        )
        infer_call_ms = (time.perf_counter() - infer_started_at) * 1000.0
        payload = infer_output_to_dict(
            out,
            {
                "detect_upload_read_ms": round(upload_read_ms, 3),
                "detect_raw_buffer_decode_ms": round(raw_decode_ms, 3),
                "detect_engine_call_ms": round(infer_call_ms, 3),
                "detect_container_handler_ms": round((time.perf_counter() - handler_started_at) * 1000.0, 3),
            },
        )
        return payload
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
