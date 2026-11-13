"""CORS chỉ nhận trang web của mình (CORS_ORIGINS); trang lạ không nhận được header cho phép.

Phụ trách: TV1 · [S4] Xác thực client, CORS, bảo vệ admin
"""

from fastapi.testclient import TestClient

from app.main import create_app
from core.config import Settings

WEB = "http://localhost:15173"


def client(ctx):
    ctx.settings = Settings(_env_file=None, environment="test", cors_origins=[WEB])
    return TestClient(create_app(ctx.settings, context=ctx))


def test_the_web_origin_is_allowed(ctx):
    with client(ctx) as c:
        res = c.get("/api/v1/health", headers={"Origin": WEB})
        pre = c.options(
            "/api/v1/chat",
            headers={
                "Origin": WEB,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert res.headers["access-control-allow-origin"] == WEB
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == WEB


def test_another_site_gets_no_cors_permission(ctx):
    with client(ctx) as c:
        res = c.get("/api/v1/health", headers={"Origin": "https://evil.example"})
        pre = c.options(
            "/api/v1/chat",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )
    assert "access-control-allow-origin" not in res.headers
    assert pre.status_code == 400 and "access-control-allow-origin" not in pre.headers


def test_methods_beyond_get_and_post_are_not_offered(ctx):
    with client(ctx) as c:
        pre = c.options("/api/v1/chat", headers={"Origin": WEB, "Access-Control-Request-Method": "DELETE"})
    assert pre.status_code == 400
