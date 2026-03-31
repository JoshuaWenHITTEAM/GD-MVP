import base64

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.inference.engine import run_preprocess
from app.model_store import health_info
from app.schemas import PreprocessInput, URLPreprocessRequest

app = FastAPI(title="Image Preprocess HTTP Service")


def preprocess_output_to_dict(out) -> dict:
    return {
        "method_name": out.method_name,
        "processed_image_base64": base64.b64encode(out.processed_image_bytes).decode("utf-8"),
        "processed_media_type": out.processed_media_type,
    }


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


@app.post("/infer/url")
def infer_by_url(req: URLPreprocessRequest):
    try:
        out = run_preprocess(
            PreprocessInput(
                method_name=req.method_name,
                image_url=req.image_url,
            )
        )
        return preprocess_output_to_dict(out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/infer/file")
async def infer_by_file(
    method_name: str = Form(...),
    image: UploadFile = File(...),
):
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="empty uploaded image")

        out = run_preprocess(
            PreprocessInput(
                method_name=method_name,
                image_bytes=image_bytes,
            )
        )
        return preprocess_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
