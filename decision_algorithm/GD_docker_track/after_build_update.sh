#!/usr/bin/env bash
set -euo pipefail

DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-algo-gd-docker-track-v1}"
NAMESPACE="${NAMESPACE:-default}"
MANAGER_URL="${MANAGER_URL:-http://localhost:8080}"

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
