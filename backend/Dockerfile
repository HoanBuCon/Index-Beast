# Image dùng cho cả API (mặc định) và lệnh ingest: docker compose run --rm api python -m ingest ...
FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MODELS_DIR=/models

WORKDIR /app
RUN python -m pip install --no-cache-dir pip==26.2.1

COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Tải sẵn model ONNX vào image để container không phải tải lúc khởi động
COPY core ./core
RUN python -m core.encoders.onnx

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips='*'"]
