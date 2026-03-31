FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_CONFIG_FILE=/dev/null \
    YOLO_CONFIG_DIR=/tmp/Ultralytics

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt /workspace/requirements-runtime.txt

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -r /workspace/requirements-runtime.txt