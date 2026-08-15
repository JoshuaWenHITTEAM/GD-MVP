# det_yolo

AntiUAV YOLO inference project with two entry modes:

- local script inference via `predict.py`
- HTTP inference service via `FastAPI + uvicorn + docker compose`

## Structure

```text
det_yolo/
├── app/
│   ├── inference/
│   ├── model_store.py
│   ├── schemas.py
│   └── server.py
├── compose.yaml
├── configs/
│   └── predict.yaml
├── detect/
│   ├── __init__.py
│   ├── config.yaml
│   ├── infer.py
│   ├── yolo_model.py
│   └── weights/
│       └── anti_uav_yolov8n.pt
├── models/
│   └── anti_uav_yolov8n.pt
├── predict.py
├── runtime.Dockerfile
├── runtime.base.Dockerfile
└── requirements-runtime.txt
```

## Script Inference

```bash
python3 -m pip install -r requirements.txt
python3 predict.py --config configs/predict.yaml --input path/to/image.jpg
```

`predict.py` and `configs/predict.yaml` are preserved as the single-image inference entrypoint.

## HTTP Service

Start the service:

```bash
DOCKERFILE=runtime.base.Dockerfile ./build_image.sh
docker compose up --build
```

For skaffold hot reload:

```bash
DOCKERFILE=runtime.base.Dockerfile ./build_image.sh
skaffold build
```

`runtime.base.Dockerfile` builds the heavy dependency base image.
`runtime.Dockerfile` only copies `app/` onto that base image for fast rebuilds.

Service endpoints:

- `GET /healthz`
- `GET /ready`
- `GET /version`
- `POST /infer/url`
- `POST /infer/file`

Example request body for `/infer/url`:

```json
{
  "model_name": "anti_uav_yolov8n",
  "image_url": "https://example.com/test.jpg"
}
```

The response schema matches the existing docker detection services:
- `model_name`
- `num_detections`
- `detections`
- `yolo_txt`
- `annotated_image_base64`
- `annotated_media_type`
