#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-gd-docker-preprocess}"
IMAGE_TAG="${IMAGE_TAG:-v1}"
DOCKERFILE="${DOCKERFILE:-runtime.Dockerfile}"
BASE_IMAGE="${BASE_IMAGE:-gd-docker-preprocess-base:arm64}"
CONTEXT_DIR="${CONTEXT_DIR:-.}"
APP_DIR="${APP_DIR:-app}"
LOAD_TO_MINIKUBE="${LOAD_TO_MINIKUBE:-false}"

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

err() {
  echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || err "未检测到 docker，请先安装并启动 Docker Desktop。"

[ -f "$DOCKERFILE" ] || err "找不到 Dockerfile: $DOCKERFILE"
[ -d "$APP_DIR" ] || err "找不到目录: $APP_DIR，请在包含 app/ 的项目根目录执行。"

if ! docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
  err "基础镜像不存在: $BASE_IMAGE
请先构建或加载基础镜像后再执行。"
fi

FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

log "开始构建镜像: $FULL_IMAGE"
log "Dockerfile: $DOCKERFILE"
log "基础镜像: $BASE_IMAGE"
log "构建上下文: $CONTEXT_DIR"

docker build \
  -f "$DOCKERFILE" \
  -t "$FULL_IMAGE" \
  "$CONTEXT_DIR"

log "构建完成: $FULL_IMAGE"

if [ "$LOAD_TO_MINIKUBE" = "true" ]; then
  command -v minikube >/dev/null 2>&1 || err "未检测到 minikube，无法执行 image load。"

  log "加载镜像到 minikube: $FULL_IMAGE"
  minikube image load "$FULL_IMAGE"
  log "已加载到 minikube"
fi

log "当前镜像信息："
docker images | grep "$(echo "$IMAGE_NAME" | sed 's/[^^]/[&]/g; s/\^/\\^/g')" || true

log "全部完成"
