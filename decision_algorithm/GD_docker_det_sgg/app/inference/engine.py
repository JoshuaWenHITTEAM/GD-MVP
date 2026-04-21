from app.inference.backends.ultralytics_yolo import run_ultralytics_detect
from app.inference.io_utils import load_image_to_bgr
from app.model_store import get_model
from app.schemas import InferInput, InferOutput


def run_infer(req: InferInput) -> InferOutput:
    model = get_model(req.model_name)
    image_bgr = load_image_to_bgr(req)
    return run_ultralytics_detect(model, image_bgr, req.model_name)