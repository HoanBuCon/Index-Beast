"""Gọi /health với PostgreSQL, Redis, Qdrant thật. Chạy: make up && pytest -m integration"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.config import Settings

pytestmark = pytest.mark.integration


def test_health_against_real_services():
    settings = Settings()  # đọc .env / biến môi trường như khi chạy thật
    with TestClient(create_app(settings)) as client:
        res = client.get("/api/v1/health")

    assert res.status_code == 200, res.json()
    assert res.json()["status"] == "ok"
