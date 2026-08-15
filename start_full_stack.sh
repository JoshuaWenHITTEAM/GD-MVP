#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT_DIR}/.run_logs"
mkdir -p "${LOG_DIR}"

CONDA_SH="${CONDA_SH:-${HOME}/anaconda3/etc/profile.d/conda.sh}"
CONDA_ENV="GD-MVP"

start_python_service() {
  local service_name="$1"
  local workdir="$2"
  local match_pattern="$3"
  local command="$4"
  local log_file="${LOG_DIR}/${service_name}.log"

  if pgrep -af "${match_pattern}" >/dev/null 2>&1; then
    echo "[skip] ${service_name} already running"
    return 0
  fi

  echo "[start] ${service_name}"
  nohup bash -lc "
    source '${CONDA_SH}'
    conda activate '${CONDA_ENV}'
    cd '${workdir}'
    exec ${command}
  " >"${log_file}" 2>&1 &
  sleep 2

  if pgrep -af "${match_pattern}" >/dev/null 2>&1; then
    echo "[ok] ${service_name} started"
  else
    echo "[fail] ${service_name} failed to start, check ${log_file}" >&2
    return 1
  fi
}

echo "[start] media-stack"
(
  cd "${ROOT_DIR}/data/media-stack"
  docker compose up -d
)
echo "[ok] media-stack ready"

echo "[start] images_build runtimes"
bash "${ROOT_DIR}/decision_algorithm/images_build/start_all.sh"
echo "[ok] images_build runtimes ready"

start_python_service \
  "training_console_backend" \
  "${ROOT_DIR}/decision_algorithm/RL_train" \
  "uvicorn training_console_backend.main:app --host 0.0.0.0 --port 30000" \
  "uvicorn training_console_backend.main:app --host 0.0.0.0 --port 30000"

start_python_service \
  "algorithm_platform_demo" \
  "${ROOT_DIR}/algorithm_platform/demo" \
  "uvicorn app:app --reload --host 0.0.0.0 --port 7000" \
  "python3 -m uvicorn app:app --reload --host 0.0.0.0 --port 7000"

start_python_service \
  "algorithm_chain_backend" \
  "${ROOT_DIR}" \
  "uvicorn decision_algorithm.algorithm_chain.backend_service:app --host 0.0.0.0 --port 8010" \
  "uvicorn decision_algorithm.algorithm_chain.backend_service:app --host 0.0.0.0 --port 8010"

start_python_service \
  "frontend_app" \
  "${ROOT_DIR}/frontend" \
  "uvicorn app.main:app --reload --port 30001" \
  "uvicorn app.main:app --reload --port 30001"

cat <<EOF

All services started or already running.

Logs:
  ${LOG_DIR}

Endpoints:
  frontend:                 http://127.0.0.1:30001
  algorithm platform demo:  http://127.0.0.1:7000
  algorithm chain backend:  http://127.0.0.1:8010
  training backend:         http://127.0.0.1:30000
  minio console:            http://127.0.0.1:9001
EOF
