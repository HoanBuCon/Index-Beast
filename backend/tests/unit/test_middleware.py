from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.main import create_app
from app.middleware import RequestContextMiddleware
from core.logging import request_id_var


def test_request_id_is_echoed_when_valid(client):
    res = client.get("/api/v1/health", headers={"X-Request-ID": "bot-123_abc.def"})

    assert res.headers["X-Request-ID"] == "bot-123_abc.def"


def test_unsafe_request_id_is_replaced(client):
    for unsafe in ("a b", "x" * 65, 'evil"}\n{"level":"ERROR'):
        res = client.get("/api/v1/health", headers={"X-Request-ID": unsafe})
        assert res.headers["X-Request-ID"] != unsafe
        assert len(res.headers["X-Request-ID"]) == 16


def test_request_id_stays_set_while_streaming():
    seen: list[str] = []

    async def stream():
        for chunk in ("a", "b"):
            seen.append(request_id_var.get())  # log trong lúc stream SSE phải còn request id
            yield chunk

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.get("/stream")(lambda: StreamingResponse(stream()))

    res = TestClient(app).get("/stream", headers={"X-Request-ID": "sse-1"})

    assert res.text == "ab"
    assert seen == ["sse-1", "sse-1"]


def test_docs_hidden_in_prod(settings, ctx):
    prod = settings.model_copy(update={"environment": "prod", "postgres_password": SecretStr("s3cret")})
    with TestClient(create_app(prod, context=ctx)) as client:
        assert client.get("/api/openapi.json").status_code == 404
        assert client.get("/api/v1/health").status_code == 200


def test_docs_served_outside_prod(client):
    assert "/api/v1/health" in client.get("/api/openapi.json").json()["paths"]
