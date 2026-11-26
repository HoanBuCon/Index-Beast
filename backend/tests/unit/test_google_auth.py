"""Đăng nhập Google OAuth2 (ADR-005): cấu hình, adapter, routes, băm ID và migration 0006. Google và DB được giả;
Discord giữ nguyên ở test_auth.py.

Phụ trách: TV1 · [S5] Đăng nhập Google
"""

import hashlib
import hmac
import importlib.util
import json
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint

from app.adapters.google_oauth import GoogleOAuth
from app.api.deps import get_google_oauth
from app.context import AppContext, register_infra
from app.main import create_app
from app.services import auth
from app.services.auth import OAUTH_COOKIE, SESSION_COOKIE
from core.config import Settings, UnsafeConfigError, ensure_safe_for_environment
from core.errors import UpstreamError
from tests.unit.test_auth import AUTH, USER

GOOGLE = {
    "google_client_id": "123-abc.apps.googleusercontent.com",
    "google_client_secret": "g-secret",
    "auth_secret": "s" * 32,
    "web_url": "http://localhost:15173",
}


def google_settings(**kw):
    return Settings(_env_file=None, environment="test", **{**GOOGLE, **kw})


# ---------- cấu hình ----------


@pytest.mark.parametrize("missing", ["google_client_id", "google_client_secret", "auth_secret"])
def test_google_login_needs_both_google_values_and_a_real_auth_secret(missing):
    assert google_settings().google_auth_enabled
    assert not google_settings(**{missing: ""}).google_auth_enabled
    assert not google_settings(**{missing: "change-me"}).google_auth_enabled
    assert not google_settings(auth_secret="too-short").google_auth_enabled


def test_google_only_still_enables_sessions_but_not_discord():
    settings = google_settings()
    assert settings.login_enabled and not settings.auth_enabled
    assert not Settings(_env_file=None).login_enabled
    discord_only = Settings(_env_file=None, environment="test", **AUTH)
    assert discord_only.login_enabled and not discord_only.google_auth_enabled


def test_google_callback_url_defaults_to_the_web_url_and_can_be_overridden():
    assert google_settings().google_callback_url == "http://localhost:15173/api/v1/auth/google/callback"
    assert google_settings(web_url="https://x.example/").google_callback_url == (
        "https://x.example/api/v1/auth/google/callback"
    )
    assert google_settings(google_redirect_uri="https://custom/cb").google_callback_url == "https://custom/cb"


def test_prod_rejects_placeholder_google_secrets_and_insecure_cookie():
    def prod(**kw):
        return Settings(
            _env_file=None,
            **{**GOOGLE, "environment": "prod", "postgres_password": "s3cret", "web_url": "https://example.org", **kw},
        )

    ensure_safe_for_environment(prod())
    with pytest.raises(UnsafeConfigError, match="GOOGLE_CLIENT_SECRET"):
        ensure_safe_for_environment(prod(google_client_secret="change-me"))
    with pytest.raises(UnsafeConfigError, match="GOOGLE_CLIENT_ID"):
        ensure_safe_for_environment(prod(google_client_id="change-me"))
    with pytest.raises(UnsafeConfigError, match="Secure"):
        ensure_safe_for_environment(prod(web_url="http://example.org"))


# ---------- băm ID ----------


def test_discord_hashes_stay_byte_identical_to_the_legacy_digest():
    settings = Settings(_env_file=None, environment="test", **AUTH)
    legacy = hmac.new(b"s" * 32, b"discord:9876543210", hashlib.sha256).hexdigest()
    assert auth.provider_hash(settings, "9876543210") == legacy
    assert auth.provider_hash(settings, "9876543210", "discord") == legacy


def test_the_same_raw_id_hashes_differently_per_provider():
    settings = google_settings()
    assert auth.provider_hash(settings, "42", "google") != auth.provider_hash(settings, "42", "discord")
    assert "42" not in auth.provider_hash(settings, "42", "google")


# ---------- adapter ----------


def test_authorize_url_has_pkce_state_openid_profile_scope_and_no_email():
    url = GoogleOAuth(google_settings()).authorize_url("the-state", "the-challenge")
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert query["client_id"] == ["123-abc.apps.googleusercontent.com"]
    assert query["redirect_uri"] == ["http://localhost:15173/api/v1/auth/google/callback"]
    assert query["response_type"] == ["code"] and query["scope"] == ["openid profile"]
    assert query["state"] == ["the-state"] and query["code_challenge"] == ["the-challenge"]
    assert query["code_challenge_method"] == ["S256"] and query["prompt"] == ["select_account"]
    assert "email" not in query["scope"][0]


async def test_google_adapter_exchanges_code_with_pkce_and_reads_sub_and_name():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.content.decode(), request.headers.get("authorization")))
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "at-1", "id_token": "ignored"})
        return httpx.Response(200, json={"sub": "110169484474386276334", "name": "Tarnished", "email": "x@y.z"})

    oauth = GoogleOAuth(google_settings(), transport=httpx.MockTransport(handler))
    token = await oauth.exchange("the-code", "the-verifier")
    assert token == "at-1" and await oauth.fetch_user(token) == ("110169484474386276334", "Tarnished")
    assert seen[0][:2] == ("POST", "https://oauth2.googleapis.com/token")
    body = parse_qs(seen[0][2])
    assert body["code"] == ["the-code"] and body["code_verifier"] == ["the-verifier"]
    assert body["grant_type"] == ["authorization_code"] and body["client_secret"] == ["g-secret"]
    assert body["redirect_uri"] == ["http://localhost:15173/api/v1/auth/google/callback"]
    assert seen[1][:2] == ("GET", "https://openidconnect.googleapis.com/v1/userinfo")
    assert seen[1][3] == "Bearer at-1"


@pytest.mark.parametrize(
    "response",
    [httpx.Response(500), httpx.Response(200, json=["not", "an", "object"]), httpx.Response(200, text="not json")],
)
async def test_google_failures_become_a_generic_502(response):
    oauth = GoogleOAuth(google_settings(), transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(UpstreamError) as caught:
        await oauth.exchange("code", "verifier")
    assert "code" not in caught.value.message and caught.value.status_code == 502


async def test_google_exchange_without_an_access_token_fails():
    oauth = GoogleOAuth(google_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(UpstreamError):
        await oauth.exchange("code", "verifier")


@pytest.mark.parametrize("body", [{}, {"sub": ""}, {"sub": 12345}, {"sub": "x" * 300}, {"name": "No sub"}])
async def test_google_user_must_have_a_valid_sub(body):
    oauth = GoogleOAuth(google_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    with pytest.raises(UpstreamError):
        await oauth.fetch_user("token")


async def test_google_user_name_is_optional_and_trimmed():
    def adapter(name):
        return GoogleOAuth(
            google_settings(),
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"sub": "1", "name": name})),
        )

    assert await adapter("  ").fetch_user("t") == ("1", None)
    assert (await adapter("n" * 200).fetch_user("t"))[1] == "n" * 80


# ---------- routes ----------


class FakeGoogle(GoogleOAuth):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls = []
        self.fail = False

    async def exchange(self, code, code_verifier):
        self.calls.append(("exchange", code, code_verifier))
        if self.fail:
            raise UpstreamError("Không kết nối được Google để đăng nhập.")
        return "access-token"

    async def fetch_user(self, access_token):
        self.calls.append(("fetch_user", access_token))
        return "110169484474386276334", "Tarnished"


class GoogleHarness:
    def __init__(self, settings, fakes, monkeypatch):
        self.stack = ExitStack()
        ctx = AppContext(settings=settings, sessionmaker=object(), **fakes)  # type: ignore[arg-type]
        register_infra(ctx)
        self.client = self.stack.enter_context(TestClient(create_app(settings, context=ctx), follow_redirects=False))
        self.oauth = FakeGoogle(settings)
        self.client.app.dependency_overrides[get_google_oauth] = lambda: self.oauth
        self.fakes, self.created, self.upserts = fakes, [], []

        async def upsert_user(sessionmaker, settings_, raw_id, display_name, provider="discord"):
            self.upserts.append((provider, raw_id, display_name))
            return USER

        async def create_session(sessionmaker, user_id, days):
            self.created.append((user_id, days))
            return "raw-session-token"

        async def user_for_token(sessionmaker, settings_, token):
            return USER if token == "raw-session-token" else None

        monkeypatch.setattr(auth, "upsert_user", upsert_user)
        monkeypatch.setattr(auth, "create_session", create_session)
        monkeypatch.setattr(auth, "user_for_token", user_for_token)

    def start_login(self, next_path="/"):
        response = self.client.get("/api/v1/auth/google/login", params={"next": next_path})
        return response, parse_qs(urlsplit(response.headers["location"]).query)


@pytest.fixture
def google(fakes, monkeypatch):
    harnesses = []

    def make(**settings):
        h = GoogleHarness(google_settings(**settings), fakes, monkeypatch)
        harnesses.append(h)
        return h

    yield make
    for h in harnesses:
        h.stack.close()


def test_google_routes_are_404_until_configured(google):
    h = google(google_client_secret="")
    assert h.client.get("/api/v1/auth/google/login").status_code == 404
    assert h.client.get("/api/v1/auth/google/callback?code=c&state=s").status_code == 404


def test_google_login_redirects_with_pkce_state_and_a_bound_cookie(google):
    h = google()
    response, query = h.start_login("/lore?q=marika")
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert query["scope"] == ["openid profile"] and query["code_challenge_method"] == ["S256"]
    state = query["state"][0]
    cookie = response.headers["set-cookie"]
    assert f"{OAUTH_COOKIE}={state}" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Path=/api/v1/auth" in cookie and response.headers["cache-control"] == "no-store"
    saved = json.loads(h.fakes["redis"].store[f"oauth:state:{auth.hash_token(state)}"])
    assert auth.pkce_challenge(saved["verifier"]) == query["code_challenge"][0]
    assert saved["next"] == "/lore?q=marika" and saved["provider"] == "google"


def test_google_login_drops_an_open_redirect_target(google):
    h = google()
    h.start_login("//evil.example/steal")
    assert json.loads(next(iter(h.fakes["redis"].store.values())))["next"] == "/"


def test_google_login_fails_closed_when_redis_is_down(google):
    h = google()
    h.fakes["redis"].fail = True
    assert h.client.get("/api/v1/auth/google/login").status_code == 503


def test_google_login_start_is_rate_limited_per_ip(google):
    h = google()
    limit = h.client.app.state.ctx.settings.rate_limit_per_minute
    codes = [h.client.get("/api/v1/auth/google/login").status_code for _ in range(limit + 2)]
    assert codes == [302] * limit + [429, 429]


def test_successful_google_callback_stores_only_the_sub_and_sets_the_session_cookie(google):
    h = google()
    _, query = h.start_login("/lore")
    response = h.client.get("/api/v1/auth/google/callback", params={"code": "the-code", "state": query["state"][0]})
    assert response.status_code == 302 and response.headers["location"] == "http://localhost:15173/lore"
    cookies = response.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith(f"{SESSION_COOKIE}="))
    assert "raw-session-token" in session and "HttpOnly" in session and "SameSite=lax" in session
    assert any(c.startswith(f"{OAUTH_COOKIE}=") and "Max-Age=0" in c for c in cookies)
    assert h.upserts == [("google", "110169484474386276334", "Tarnished")] and h.created == [(USER.id, 7)]
    exchange = next(c for c in h.oauth.calls if c[0] == "exchange")
    assert auth.pkce_challenge(exchange[2]) == query["code_challenge"][0]
    assert h.fakes["redis"].store == {}


def test_google_callback_rejects_a_missing_or_foreign_state(google):
    h = google()
    _, query = h.start_login()
    state = query["state"][0]
    h.client.cookies.clear()
    assert h.client.get("/api/v1/auth/google/callback", params={"code": "c", "state": state}).status_code == 400
    h.client.cookies.set(OAUTH_COOKIE, "another-state")
    assert h.client.get("/api/v1/auth/google/callback", params={"code": "c", "state": state}).status_code == 400
    assert h.created == [] and h.oauth.calls == []


def test_google_callback_state_is_single_use(google):
    h = google()
    _, query = h.start_login()
    params = {"code": "c", "state": query["state"][0]}
    assert h.client.get("/api/v1/auth/google/callback", params=params).status_code == 302
    h.client.cookies.set(OAUTH_COOKIE, params["state"])
    assert h.client.get("/api/v1/auth/google/callback", params=params).status_code == 400
    assert len(h.created) == 1


def test_a_state_started_for_another_provider_is_refused(google):
    h = google()
    state = "discord-state"
    h.fakes["redis"].__dict__.setdefault("store", {})[f"oauth:state:{auth.hash_token(state)}"] = json.dumps(
        {"verifier": "v", "next": "/"}
    )
    h.client.cookies.set(OAUTH_COOKIE, state)
    assert h.client.get("/api/v1/auth/google/callback", params={"code": "c", "state": state}).status_code == 400
    assert h.oauth.calls == []


def test_a_google_state_is_refused_by_the_discord_callback(google):
    h = google(**AUTH)  # cả hai nhà cung cấp cùng bật
    _, query = h.start_login()
    state = query["state"][0]
    assert h.client.get("/api/v1/auth/discord/callback", params={"code": "c", "state": state}).status_code == 400
    assert h.created == []


def test_google_callback_without_a_code_is_rejected_and_denial_goes_back_with_a_flag(google):
    h = google()
    _, query = h.start_login()
    state = query["state"][0]
    assert h.client.get("/api/v1/auth/google/callback", params={"state": state}).status_code == 400
    denied = h.client.get("/api/v1/auth/google/callback", params={"error": "access_denied", "state": state})
    assert denied.status_code == 302 and denied.headers["location"] == "http://localhost:15173/?login=denied"
    assert h.created == []


def test_a_google_failure_creates_no_session(google):
    h = google()
    h.oauth.fail = True
    _, query = h.start_login()
    response = h.client.get("/api/v1/auth/google/callback", params={"code": "c", "state": query["state"][0]})
    assert response.status_code == 502 and SESSION_COOKIE not in response.headers.get("set-cookie", "")
    assert h.created == []


def test_google_only_deployment_reports_capabilities_and_keeps_discord_404(google):
    h = google()
    body = h.client.get("/api/v1/chat/capabilities").json()
    assert body["google_auth_available"] is True and body["auth_available"] is False
    assert h.client.get("/api/v1/auth/discord/login").status_code == 404


def test_google_only_deployment_still_reads_the_session_cookie(google):
    h = google()
    h.client.cookies.set(SESSION_COOKIE, "raw-session-token")
    assert h.client.get("/api/v1/auth/me").json()["authenticated"] is True


def test_google_users_are_never_admins():
    settings = google_settings(auth_admin_discord_ids="110169484474386276334")
    assert auth.provider_hash(settings, "110169484474386276334", "google") not in auth.admin_hashes(settings)


# ---------- migration 0006 ----------


def _migration():
    path = Path(__file__).parents[2] / "migrations" / "versions" / "0006_google_provider.py"
    spec = importlib.util.spec_from_file_location("migration_0006", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0006_follows_0005_and_is_reversible():
    module = _migration()
    assert (module.revision, module.down_revision) == ("0006", "0005")
    assert callable(module.upgrade) and callable(module.downgrade)


def test_the_user_model_allows_google():
    from core.db.models import User

    checks = [c for c in User.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("'google'" in str(c.sqltext) and "'discord'" in str(c.sqltext) for c in checks)
