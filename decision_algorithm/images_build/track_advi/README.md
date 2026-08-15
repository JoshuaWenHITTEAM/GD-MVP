# track_advi

AntiUAV AVTrack inference project packaged as a GD_docker_track-style HTTP service.

## Structure

```text
track_advi/
├── app/
├── configs/
│   └── avtrack_deit_tiny_patch16_224.yaml
├── lib/
├── models/
│   └── avtrack_ep0300.pth.tar
├── compose.yaml
├── runtime.base.Dockerfile
├── runtime.Dockerfile
├── build_image.sh
├── after_build_update.sh
├── skaffold.yaml
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

`runtime.base.Dockerfile` builds the heavy dependency base image.
`runtime.Dockerfile` copies `app/`, `lib/`, and `configs/` onto that base image for fast rebuilds.
`skaffold.yaml` is configured for hot update, with sync rules for `app/`, `lib/`, and `configs/`.

The directory has been trimmed to inference-only content. Training outputs, evaluation dumps, and legacy experiment artifacts are not retained.

## Endpoints

- `GET /healthz`
- `GET /ready`
- `GET /version`
- `POST /template/set/file`
- `POST /template/set/url`
- `POST /template/replace/file`
- `POST /template/replace/url`
- `POST /init/file`
- `POST /init/url`
- `POST /track/file`
- `POST /track/url`
