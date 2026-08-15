#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

CONTAINERS=(
  antiuav-det-yolo-runtime
  antiuav-det-redetr-runtime
  track-advi-runtime-dev
  track-siamrpnpp-runtime-dev
  pre-clahe-runtime-dev
  pre-unsharp-runtime-dev
)

for name in "${CONTAINERS[@]}"; do
  if docker ps -a --format '{{.Names}}' | grep -Fxq "${name}"; then
    docker rm -f "${name}" >/dev/null
  fi
done

docker compose up -d
