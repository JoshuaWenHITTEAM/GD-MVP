# track_siamRPN++

Inference-only SiamRPN++ AntiUAV tracking project packaged as a `GD_docker_track`-style HTTP service.

## Structure

```text
track_siamRPN++/
├── app/
├── configs/
│   ├── siamrpnpp.yaml
│   └── predict.yaml
├── models/
│   ├── README.md
│   └── siamrpnpp.pth
├── pysot/
├── tests/
├── predict.py
├── compose.yaml
├── runtime.base.Dockerfile
├── runtime.Dockerfile
├── build_image.sh
├── after_build_update.sh
├── skaffold.yaml
├── requirements.txt
└── requirements-runtime.txt
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

`runtime.base.Dockerfile` installs the heavy runtime dependencies on top of the PyTorch base image.
`runtime.Dockerfile` only copies `app/`, `pysot/`, and `configs/` onto that base image for fast rebuilds.
`skaffold.yaml` is configured for hot update with sync rules for `app/`, `pysot/`, and `configs/`.

## Predict CLI

```bash
python3 predict.py --config configs/predict.yaml
```

Override paths when needed:

```bash
python3 predict.py \
  --config configs/predict.yaml \
  --sequence-dir ../Anti-UAV-Tracking-V0/Anti-UAV-Tracking-V0/video01 \
  --gt-file ../Anti-UAV-Tracking-V0/Anti-UAV-Tracking-V0GT/video01_gt.txt \
  --num-frames 20
```

## Endpoints

- `GET /healthz`
- `GET /ready`
- `GET /version`
- `POST /template/set/file`
- `POST /template/set/url`
- `POST /template/reset`
- `POST /template/replace/file`
- `POST /template/replace/url`
- `POST /init/file`
- `POST /init/url`
- `POST /track/file`
- `POST /track/url`
