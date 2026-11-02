# Image dùng cho cả API (mặc định) và lệnh ingest: docker compose run --rm api python -m ingest ...
# Stage 1 cài thư viện vào venv; stage 2 chỉ copy venv + code → image gọn, không có pip cache/build tool.

FROM python:3.11.9-slim-bookworm AS deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv && /opt/venv/bin/pip install pip==26.2.1
COPY requirements.txt constraints.txt ./
RUN /opt/venv/bin/pip install -r requirements.txt -c constraints.txt


FROM python:3.11.9-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODELS_DIR=/models
RUN useradd --create-home --uid 10001 app && mkdir -p /models /app/data && chown app:app /models /app/data
COPY --from=deps /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app . .
USER app

# S2 (TV3): tải sẵn model ONNX vào /models ở bước build — `RUN python -m core.encoders.onnx`
# S2 (TV1): chạy migration trước khi khởi động — `alembic upgrade head && uvicorn ...`
# Số worker: biến WEB_CONCURRENCY (compose đặt từ API_WORKERS trong .env)
# Cổng nội bộ 18000 (không dùng 8000 mặc định của uvicorn — docs/quy_uoc.md → "Quy ước cổng")
EXPOSE 18000
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "18000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
