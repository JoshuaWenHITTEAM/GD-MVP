#!/usr/bin/env bash
set -euo pipefail

docker build -f runtime.base.Dockerfile -t pre-clahe-base:latest .
docker build -f runtime.Dockerfile -t pre-clahe-runtime:latest .
