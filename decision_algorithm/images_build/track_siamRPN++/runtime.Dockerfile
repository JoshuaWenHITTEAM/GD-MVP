FROM track-siamrpnpp-base:arm64

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY app /workspace/app
COPY pysot /workspace/pysot
COPY configs /workspace/configs

EXPOSE 8000

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
