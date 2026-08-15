from app.inference.backends.ultralytics_yolo import run_ultralytics_detect
from app.inference.io_utils import load_image_to_bgr
from app.model_store import get_model, normalize_model_name
from app.schemas import InferInput, InferOutput


def run_infer(req: InferInput) -> InferOutput:
    safe_model_name = normalize_model_name(req.model_name)
    model = get_model(safe_model_name)
    image_bgr = load_image_to_bgr(req)
    return run_ultralytics_detect(
        model,
        image_bgr,
        safe_model_name,
        return_image=req.return_image,
        return_yolo_txt=req.return_yolo_txt,
    )
