#!/usr/bin/env bash
set -euo pipefail

DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-algo-gd-docker-det-v1-c0b90a59}"
NAMESPACE="${NAMESPACE:-default}"
MANAGER_URL="${MANAGER_URL:-http://localhost:8080}"

# Skaffold hook 环境里常见会提供镜像相关环境变量；
# 但不同 hook 场景下可用变量要以实际日志为准。
# 为了稳妥，这里先把环境打印出来排查一次。
echo "==> available env (filtered)"
env | grep -E 'SKAFFOLD|IMAGE' || true

IMAGE_REF="${SKAFFOLD_IMAGE:-}"
if [ -z "$IMAGE_REF" ]; then
  echo "SKAFFOLD_IMAGE is empty"
  exit 1
fi

echo "==> built image: ${IMAGE_REF}"

curl -f -X POST \
  "${MANAGER_URL}/api/v1/containers/${DEPLOYMENT_NAME}/image?namespace=${NAMESPACE}" \
  -H "Content-Type: application/json" \
  -d "{\"image\":\"${IMAGE_REF}\"}"

echo
echo "==> wait rollout"
kubectl rollout status deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}"
kubectl get pods -n "${NAMESPACE}" -o wide