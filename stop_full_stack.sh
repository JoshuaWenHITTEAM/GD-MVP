#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

stop_python_service() {
  local service_name="$1"
  local match_pattern="$2"
  local pids

  pids="$(pgrep -f "${match_pattern}" || true)"
  if [[ -z "${pids}" ]]; then
    echo "[skip] ${service_name} not running"
    return 0
  fi

  echo "[stop] ${service_name}"
  kill ${pids} || true
  sleep 2

  pids="$(pgrep -f "${match_pattern}" || true)"
  if [[ -n "${pids}" ]]; then
    kill -9 ${pids} || true
  fi
  echo "[ok] ${service_name} stopped"
}

stop_python_service \
  "frontend_app" \
  "uvicorn app.main:app --reload --port 30001"

stop_python_service \
  "algorithm_chain_backend" \
  "uvicorn decision_algorithm.algorithm_chain.backend_service:app --host 0.0.0.0 --port 8010"

stop_python_service \
  "algorithm_platform_demo" \
  "uvicorn app:app --reload --host 0.0.0.0 --port 7000"

stop_python_service \
  "training_console_backend" \
  "uvicorn training_console_backend.main:app --host 0.0.0.0 --port 30000"

echo "[stop] images_build runtimes"
bash "${ROOT_DIR}/decision_algorithm/images_build/stop_all.sh"
echo "[ok] images_build runtimes stopped"

echo "[stop] media-stack"
(
  cd "${ROOT_DIR}/data/media-stack"
  docker compose down
)
echo "[ok] media-stack stopped"

echo
echo "All services stopped."
