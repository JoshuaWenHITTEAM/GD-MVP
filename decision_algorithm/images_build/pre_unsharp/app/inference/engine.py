from app.inference.backends.unsharp_runtime import run_unsharp
from app.inference.io_utils import load_image_to_bgr
from app.schemas import InferInput, InferOutput


def run_infer(req: InferInput) -> InferOutput:
    image_bgr = load_image_to_bgr(req)
    return run_unsharp(
        image_bgr,
        req.model_name,
        return_image=req.return_image,
    )
