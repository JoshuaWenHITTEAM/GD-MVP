import base64

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.inference.engine import run_infer
from app.model_store import health_info
from app.schemas import InferInput, URLInferRequest

app = FastAPI(title="AntiUAV RT-DETR HTTP Inference Service")


def infer_output_to_dict(out) -> dict:
    payload = {
        "model_name": out.model_name,
        "num_detections": out.num_detections,
        "detections": out.detections,
    }
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
    return {"version": "det-redetr-http-v1"}


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
