from app.inference.backends.preprocess_ops import apply_preprocess
from app.inference.io_utils import encode_rgb_to_jpeg_bytes, load_image_to_rgb
from app.model_store import get_weighted_model, normalize_method_name
from app.schemas import PreprocessInput, PreprocessOutput


def run_preprocess(req: PreprocessInput) -> PreprocessOutput:
    method_name = normalize_method_name(req.method_name)
    model = get_weighted_model(method_name)
    image_rgb = load_image_to_rgb(req)
    processed_rgb = apply_preprocess(method_name, image_rgb, model=model)
    processed_image_bytes = encode_rgb_to_jpeg_bytes(processed_rgb)
    return PreprocessOutput(
        method_name=method_name,
        processed_image_bytes=processed_image_bytes,
        processed_media_type="image/jpeg",
    )

