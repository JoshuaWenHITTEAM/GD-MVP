import base64

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.inference.engine import run_infer
from app.model_store import health_info
from app.schemas import InferInput, URLInferRequest

app = FastAPI(title="Preprocess CLAHE HTTP Inference Service")


def infer_output_to_dict(out) -> dict:
    payload = {
        "model_name": out.model_name,
        "operation": out.operation,
        "metadata": out.metadata or {},
    }
    if out.processed_image_bytes is not None:
        payload["processed_image_base64"] = base64.b64encode(out.processed_image_bytes).decode("utf-8")
        payload["processed_media_type"] = out.processed_media_type
    return payload


@app.get("/healthz")
def healthz():
    return {"status": "ok", **health_info()}


@app.get("/ready")
def ready():
    return {"status": "ready", **health_info()}


@app.get("/version")
def version():
    return {"version": "pre-clahe-http-v1"}


@app.post("/infer/url")
def infer_by_url(req: URLInferRequest):
    try:
        out = run_infer(
            InferInput(
                model_name=req.model_name,
                image_url=req.image_url,
                return_image=req.return_image,
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
            )
        )
        return infer_output_to_dict(out)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
