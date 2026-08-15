# det_redetr

AntiUAV RT-DETR inference project with two entry modes:

- local inference CLI via `main.py`
- single-image inference via `predict.py`
- HTTP inference service via `FastAPI + uvicorn + docker compose`

## Structure

```text
det_redetr/
├── app/
│   ├── inference/
│   ├── model_store.py
│   ├── schemas.py
│   └── server.py
├── compose.yaml
├── configs/
│   └── predict.yaml
├── main.py
├── predict.py
├── models/
│   └── anti_uav_rtdetr.pt
├── runtime.Dockerfile
├── runtime.base.Dockerfile
└── requirements-runtime.txt
```

## CLI

```bash
python3 -m pip install -r requirements.txt
python3 main.py --model models/anti_uav_rtdetr.pt --source path/to/image.jpg
python3 predict.py --config configs/predict.yaml --input path/to/image.jpg
```

## HTTP Service

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

Example `/infer/url` body:

```json
{
  "model_name": "anti_uav_rtdetr",
  "image_url": "https://example.com/test.jpg"
}
```
