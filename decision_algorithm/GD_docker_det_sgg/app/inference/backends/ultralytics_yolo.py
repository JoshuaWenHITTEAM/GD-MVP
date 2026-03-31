from app.inference.io_utils import build_yolo_txt, encode_bgr_to_jpeg_bytes
from app.schemas import InferOutput


def run_ultralytics_detect(model, image_bgr, model_name: str) -> InferOutput:
    results = model.predict(source=image_bgr, verbose=False)
    if not results:
        raise ValueError("model returned empty results")

    result = results[0].cpu()
    print("predict code have been changed,test hot update")
    detections = result.summary(normalize=False, decimals=5)
    yolo_txt = build_yolo_txt(result)
    annotated_bgr = result.plot()
    annotated_image_bytes = encode_bgr_to_jpeg_bytes(annotated_bgr)

    return InferOutput(
        model_name=model_name,
        num_detections=len(result),
        detections=detections,
        yolo_txt=yolo_txt,
        annotated_image_bytes=annotated_image_bytes,
        annotated_media_type="image/jpeg",
    )