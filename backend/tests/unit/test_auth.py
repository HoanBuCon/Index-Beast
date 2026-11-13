"""Đăng nhập Discord OAuth2 (ADR-005): cấu hình, PKCE/state/next, vòng đăng nhập, cookie, CSRF, quyền admin theo phiên,
gắn người dùng vào /chat. Discord và DB được giả; phần SQL thật nằm ở tests/integration/test_auth_store.py.

Phụ trách: TV1 · [S4] Auth service
"""

import json
from contextlib import ExitStack
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.adapters.discord_oauth import DiscordOAuth
from app.api.deps import get_chat_service, get_discord_oauth
from app.context import AppContext, register_infra
from app.main import create_app
from app.services import auth
from app.services.auth import OAUTH_COOKIE, SESSION_COOKIE, AuthUser
from core.config import Settings
from core.errors import UpstreamError

AUTH = {
    "discord_client_id": "1234567890",
    "discord_client_secret": "client-secret",
    "auth_secret": "s" * 32,
    "web_url": "http://localhost:15173",
}
USER = AuthUser(uuid4(), "Tarnished", False)
ADMIN = AuthUser(uuid4(), "Melina", True)


def make_settings(**kw):
    return Settings(_env_file=None, environment="test", **{**AUTH, **kw})


# ---------- hàm thuần ----------


def test_pkce_matches_the_rfc_7636_example():
    assert auth.pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("/", "/"),
        ("/chat?x=1", "/chat?x=1"),
        (None, "/"),
        ("", "/"),
        ("//evil.example", "/"),
        ("https://evil.example", "/"),
        ("/\\evil.example", "/"),
        ("javascript:alert(1)", "/"),
        ("/ok\nSet-Cookie: x=1", "/"),
    ],
)
def test_next_only_accepts_a_relative_path(value, expected):
    assert auth.safe_next(value) == expected


def test_provider_hash_is_keyed_and_never_the_raw_id():
    a, b = make_settings(), make_settings(auth_secret="t" * 32)
    digest = auth.provider_hash(a, "9876543210")
    assert digest == auth.provider_hash(a, "9876543210") and digest != auth.provider_hash(b, "9876543210")
    assert "9876543210" not in digest and len(digest) == 64


def test_session_tokens_are_stored_only_as_hashes():
    assert auth.hash_token("abc") != "abc" and len(auth.hash_token("abc")) == 64


# ---------- cấu hình ----------


@pytest.mark.parametrize("missing", ["discord_client_id", "discord_client_secret", "auth_secret"])
def test_login_needs_all_three_real_values(missing):
    assert make_settings().auth_enabled
    assert not make_settings(**{missing: ""}).auth_enabled
    assert not make_settings(**{missing: "change-me"}).auth_enabled


def test_callback_url_and_cookie_security_follow_the_web_url():
    assert make_settings().auth_callback_url == "http://localhost:15173/api/v1/auth/discord/callback"
    assert not make_settings().auth_cookie_is_secure
    https = make_settings(web_url="https://beast.example.com/")
    assert https.auth_callback_url == "https://beast.example.com/api/v1/auth/discord/callback"
    assert (
        https.auth_cookie_is_secure
        and not make_settings(auth_cookie_secure=False, web_url="https://x").auth_cookie_is_secure
    )
    assert make_settings(auth_redirect_uri="https://custom/cb").auth_callback_url == "https://custom/cb"
    assert (
        Settings(_env_file=None, auth_cookie_secure="").auth_cookie_secure is None
    )  # docker compose truyền chuỗi rỗng


def test_admin_ids_are_numeric_and_comma_separated():
    assert make_settings(auth_admin_discord_ids="111, 222").auth_admin_discord_ids == ["111", "222"]
    assert make_settings(auth_admin_discord_ids="").auth_admin_discord_ids == []
    with pytest.raises(ValidationError):
        make_settings(auth_admin_discord_ids="111,not-a-number")


def test_admin_hashes_are_empty_when_login_is_disabled():
    assert auth.admin_hashes(Settings(_env_file=None, auth_admin_discord_ids="111")) == frozenset()
    assert auth.provider_hash(make_settings(), "111") in auth.admin_hashes(make_settings(auth_admin_discord_ids="111"))


# ---------- adapter Discord ----------


async def test_discord_adapter_exchanges_code_with_pkce_and_reads_the_user():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.content.decode(), request.headers.get("authorization")))
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "at-1"})
        return httpx.Response(200, json={"id": "424242", "username": "tarnished", "global_name": "Tarnished"})

    oauth = DiscordOAuth(make_settings(), transport=httpx.MockTransport(handler))
    token = await oauth.exchange("the-code", "the-verifier")
    assert token == "at-1" and await oauth.fetch_user(token) == ("424242", "Tarnished")
    body = parse_qs(seen[0][2])
    assert body["code_verifier"] == ["the-verifier"] and body["grant_type"] == ["authorization_code"]
    assert body["redirect_uri"] == ["http://localhost:15173/api/v1/auth/discord/callback"]
    assert seen[0][3].startswith("Basic ") and seen[1][3] == "Bearer at-1"


@pytest.mark.parametrize(
    "response",
    [httpx.Response(500), httpx.Response(200, json=["not", "an", "object"]), httpx.Response(200, text="not json")],
)
async def test_discord_failures_become_a_generic_502(response):
    oauth = DiscordOAuth(make_settings(), transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(UpstreamError) as caught:
        await oauth.exchange("code", "verifier")
    assert "code" not in caught.value.message and caught.value.status_code == 502


async def test_discord_user_must_have_a_numeric_id():
    oauth = DiscordOAuth(
        make_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"id": "x1"}))
    )
    with pytest.raises(UpstreamError):
        await oauth.fetch_user("token")


# ---------- routes ----------


class FakeOAuth(DiscordOAuth):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls = []
        self.fail = False

    async def exchange(self, code, code_verifier):
        self.calls.append(("exchange", code, code_verifier))
        if self.fail:
            raise UpstreamError("Không kết nối được Discord để đăng nhập.")
        return "access-token"

    async def fetch_user(self, access_token):
        self.calls.append(("fetch_user", access_token))
        return "424242", "Tarnished"


class Harness:
    def __init__(self, settings, fakes, monkeypatch, user=None):
        self.stack = ExitStack()
        ctx = AppContext(settings=settings, sessionmaker=object(), **fakes)  # type: ignore[arg-type]
        register_infra(ctx)
        self.client = self.stack.enter_context(TestClient(create_app(settings, context=ctx), follow_redirects=False))
        self.oauth = FakeOAuth(settings)
        self.client.app.dependency_overrides[get_discord_oauth] = lambda: self.oauth
        self.fakes, self.ended, self.user = fakes, [], user
        self.created = []

        async def upsert_user(sessionmaker, settings_, discord_id, display_name):
            return USER

        async def create_session(sessionmaker, user_id, days):
            self.created.append((user_id, days))
            return "raw-session-token"

        async def user_for_token(sessionmaker, settings_, token):
            return self.user if token == "raw-session-token" else None

        async def end_session(sessionmaker, token):
            self.ended.append(token)

        monkeypatch.setattr(auth, "upsert_user", upsert_user)
        monkeypatch.setattr(auth, "create_session", create_session)
        monkeypatch.setattr(auth, "user_for_token", user_for_token)
        monkeypatch.setattr(auth, "end_session", end_session)

    def start_login(self, next_path="/"):
        response = self.client.get("/api/v1/auth/discord/login", params={"next": next_path})
        query = parse_qs(urlsplit(response.headers["location"]).query)
        return response, query


@pytest.fixture
def harness(fakes, monkeypatch):
    harnesses = []

    def make(user=None, **settings):
        h = Harness(make_settings(**settings), fakes, monkeypatch, user)
        harnesses.append(h)
        return h

    yield make
    for h in harnesses:
        h.stack.close()


def test_login_is_404_until_discord_is_configured(harness):
    h = harness(discord_client_secret="")
    assert h.client.get("/api/v1/auth/discord/login").status_code == 404
    assert h.client.get("/api/v1/auth/discord/callback?code=c&state=s").status_code == 404


def test_login_redirects_to_discord_with_pkce_state_and_a_bound_cookie(harness):
    h = harness()
    response, query = h.start_login("/lore?q=marika")
    assert response.status_code == 302 and response.headers["location"].startswith(
        "https://discord.com/oauth2/authorize?"
    )
    assert (
        query["client_id"] == ["1234567890"] and query["scope"] == ["identify"] and query["response_type"] == ["code"]
    )
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["http://localhost:15173/api/v1/auth/discord/callback"]
    state = query["state"][0]
    cookie = response.headers["set-cookie"]
    assert f"{OAUTH_COOKIE}={state}" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Path=/api/v1/auth" in cookie and "Secure" not in cookie  # web_url là http
    saved = json.loads(h.fakes["redis"].store[f"oauth:state:{auth.hash_token(state)}"])
    assert auth.pkce_challenge(saved["verifier"]) == query["code_challenge"][0] and saved["next"] == "/lore?q=marika"


def test_login_cookie_is_secure_on_https(harness):
    h = harness(web_url="https://beast.example.com")
    response, _ = h.start_login()
    assert "Secure" in response.headers["set-cookie"]


def test_login_drops_an_open_redirect_target(harness):
    h = harness()
    _, query = h.start_login("//evil.example/steal")
    saved = json.loads(next(iter(h.fakes["redis"].store.values())))
    assert saved["next"] == "/" and "evil" not in json.dumps(saved)


def test_login_fails_closed_when_redis_is_down(harness):
    h = harness()
    h.fakes["redis"].fail = True
    assert h.client.get("/api/v1/auth/discord/login").status_code == 503


def test_successful_callback_sets_the_session_cookie_and_goes_back_to_the_web(harness):
    h = harness()
    _, query = h.start_login("/lore")
    state = query["state"][0]
    response = h.client.get("/api/v1/auth/discord/callback", params={"code": "the-code", "state": state})
    assert response.status_code == 302 and response.headers["location"] == "http://localhost:15173/lore"
    cookies = response.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith(f"{SESSION_COOKIE}="))
    assert "raw-session-token" in session and "HttpOnly" in session and "SameSite=lax" in session
    assert "Max-Age=604800" in session and "Path=/" in session
    assert any(c.startswith(f"{OAUTH_COOKIE}=") and "Max-Age=0" in c for c in cookies)  # cookie state bị xóa
    assert h.created == [(USER.id, 7)]
    exchange = next(c for c in h.oauth.calls if c[0] == "exchange")
    assert exchange[1] == "the-code" and auth.pkce_challenge(exchange[2]) == query["code_challenge"][0]
    assert h.fakes["redis"].store == {}  # state đã dùng


def test_callback_rejects_a_missing_or_foreign_state(harness):
    h = harness()
    _, query = h.start_login()
    state = query["state"][0]
    h.client.cookies.clear()  # không có cookie state: người khác đưa link cho nạn nhân
    assert h.client.get("/api/v1/auth/discord/callback", params={"code": "c", "state": state}).status_code == 400
    h.client.cookies.set(OAUTH_COOKIE, "another-state")
    assert h.client.get("/api/v1/auth/discord/callback", params={"code": "c", "state": state}).status_code == 400
    assert h.created == [] and h.oauth.calls == []


def test_callback_state_is_single_use(harness):
    h = harness()
    _, query = h.start_login()
    params = {"code": "c", "state": query["state"][0]}
    assert h.client.get("/api/v1/auth/discord/callback", params=params).status_code == 302
    h.client.cookies.set(OAUTH_COOKIE, params["state"])  # kẻ tấn công phát lại cả cookie
    assert h.client.get("/api/v1/auth/discord/callback", params=params).status_code == 400
    assert len(h.created) == 1


def test_callback_without_a_code_is_rejected_and_denial_goes_back_with_a_flag(harness):
    h = harness()
    _, query = h.start_login()
    state = query["state"][0]
    assert h.client.get("/api/v1/auth/discord/callback", params={"state": state}).status_code == 400
    denied = h.client.get("/api/v1/auth/discord/callback", params={"error": "access_denied", "state": state})
    assert denied.status_code == 302 and denied.headers["location"] == "http://localhost:15173/?login=denied"
    assert h.created == []


def test_a_discord_failure_creates_no_session(harness):
    h = harness()
    h.oauth.fail = True
    _, query = h.start_login()
    response = h.client.get("/api/v1/auth/discord/callback", params={"code": "c", "state": query["state"][0]})
    assert response.status_code == 502 and SESSION_COOKIE not in response.headers.get("set-cookie", "")
    assert h.created == []


def test_me_reports_the_session_user_or_nothing(harness):
    h = harness(user=USER)
    assert h.client.get("/api/v1/auth/me").json() == {"authenticated": False, "user": None}
    h.client.cookies.set(SESSION_COOKIE, "raw-session-token")
    body = h.client.get("/api/v1/auth/me").json()
    assert body["authenticated"] and body["user"] == {
        "id": str(USER.id),
        "display_name": "Tarnished",
        "is_admin": False,
    }
    h.client.cookies.set(SESSION_COOKIE, "forged-token")
    assert h.client.get("/api/v1/auth/me").json()["authenticated"] is False


def test_my_conversations_requires_a_session(harness):
    h = harness(user=USER)
    assert h.client.get("/api/v1/me/conversations").status_code == 401
    assert (
        h.client.post(
            "/api/v1/me/conversations/claim", json={"conversation_id": str(uuid4()), "conversation_token": "t" * 40}
        ).status_code
        == 401
    )


def test_logout_deletes_the_session_and_rejects_a_foreign_origin(harness):
    h = harness(user=USER)
    h.client.cookies.set(SESSION_COOKIE, "raw-session-token")
    assert h.client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    assert h.ended == []
    ok = h.client.post("/api/v1/auth/logout", headers={"Origin": "http://localhost:15173"})
    assert ok.status_code == 204 and h.ended == ["raw-session-token"]
    assert f"{SESSION_COOKIE}=" in ok.headers["set-cookie"] and "Max-Age=0" in ok.headers["set-cookie"]
    assert h.client.post("/api/v1/auth/logout").status_code == 204  # không có Origin (curl) vẫn được


# ---------- quyền admin theo phiên ----------


def test_a_logged_in_admin_reaches_admin_routes_without_the_token(harness):
    h = harness(user=ADMIN, auth_admin_discord_ids="424242")  # ADMIN_TOKEN không đặt
    anonymous = h.client.get(f"/api/v1/admin/trace/{uuid4()}")
    assert anonymous.status_code == 404  # tắt hẳn như trước
    h.client.cookies.set(SESSION_COOKIE, "raw-session-token")
    h.client.app.dependency_overrides[get_chat_service] = lambda: type("S", (), {"trace": staticmethod(_no_trace)})()
    assert h.client.get(f"/api/v1/admin/trace/{uuid4()}").status_code == 404  # qua cổng, hết ở "không có trace"
    assert h.client.get(f"/api/v1/admin/trace/{uuid4()}").json()["code"] == "not_found"


async def _no_trace(_message_id):
    from core.errors import NotFoundError

    raise NotFoundError("Không tìm thấy trace của câu trả lời này.")


def test_a_logged_in_non_admin_still_needs_the_token(harness):
    h = harness(user=USER, admin_token="s3cret-token")
    h.client.cookies.set(SESSION_COOKIE, "raw-session-token")
    assert h.client.get(f"/api/v1/admin/trace/{uuid4()}").status_code == 401
    h.client.cookies.clear()
    assert h.client.get(f"/api/v1/admin/trace/{uuid4()}", headers={"X-Admin-Token": "wrong"}).status_code == 401


# ---------- /chat gắn người dùng ----------


class CaptureService:
    def __init__(self):
        self.seen = []

    async def answer(self, req):
        self.seen.append(req.user_id)

        from app.api.schemas.chat import ChatResponse

        return ChatResponse(
            conversation_id=uuid4(), message_id=uuid4(), answer="ok", sources=[], grounded=False, latency_ms=1
        )


def test_chat_attaches_the_session_user_and_ignores_a_client_supplied_user_id(harness):
    h = harness(user=USER, chat_mode="rag")
    service = CaptureService()
    h.client.app.dependency_overrides[get_chat_service] = lambda: service
    body = {"message": "Marika là ai?", "channel": "web", "user_id": str(uuid4())}
    h.client.post("/api/v1/chat", json=body)
    h.client.cookies.set(SESSION_COOKIE, "raw-session-token")
    h.client.post("/api/v1/chat", json=body)
    assert service.seen == [None, USER.id]


def test_capabilities_announce_login_only_when_configured(harness):
    assert harness().client.get("/api/v1/chat/capabilities").json()["auth_available"] is True
    assert harness(discord_client_secret="").client.get("/api/v1/chat/capabilities").json()["auth_available"] is False


def test_login_start_is_rate_limited_per_ip(harness):
    h = harness()
    limit = h.client.app.state.ctx.settings.rate_limit_per_minute
    codes = [h.client.get("/api/v1/auth/discord/login").status_code for _ in range(limit + 2)]
    assert codes == [302] * limit + [429, 429]


def test_a_short_auth_secret_keeps_login_off():
    assert make_settings().auth_enabled
    assert not make_settings(auth_secret="too-short").auth_enabled
