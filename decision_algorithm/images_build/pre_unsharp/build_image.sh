#!/usr/bin/env bash
set -euo pipefail

docker build -f runtime.base.Dockerfile -t pre-unsharp-base:latest .
docker build -f runtime.Dockerfile -t pre-unsharp-runtime:latest .
