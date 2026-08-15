FROM antiuav-det-yolo-base:arm64

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/workspace \
    YOLO_CONFIG_DIR=/tmp/Ultralytics

COPY app /workspace/app

EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
