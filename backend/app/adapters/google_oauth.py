"""Gọi Google OAuth2 / OpenID Connect (authorization code + PKCE, scope `openid profile`, KHÔNG xin email): dựng URL
cho người dùng, đổi mã lấy access token, đọc `sub` (ID ổn định) và tên. Chỉ nói chuyện với Google; lỗi mạng hoặc dữ
liệu lạ trả UpstreamError (502), không lộ chi tiết và không ghi token vào log.

Phụ trách: TV1 · [S5] Đăng nhập Google (ADR-005)
"""

import logging
from urllib.parse import urlencode

import httpx

from core.config import Settings
from core.errors import UpstreamError

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
TIMEOUT_SECONDS = 10
MAX_SUB_CHARS = 255  # Google đảm bảo `sub` là chuỗi ASCII tối đa 255 ký tự


class GoogleOAuth:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport  # test thay bằng MockTransport

    def authorize_url(self, state: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_callback_url,
                "response_type": "code",
                "scope": "openid profile",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange(self, code: str, code_verifier: str) -> str:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.google_callback_url,
            "code_verifier": code_verifier,
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret.get_secret_value(),
        }
        body = await self._request("POST", TOKEN_URL, data=data)
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise UpstreamError("Google không trả access token hợp lệ.")
        return token

    async def fetch_user(self, access_token: str) -> tuple[str, str | None]:
        """(`sub`, tên hiển thị). `sub` là chuỗi ổn định, không phải email; tên có thể trống."""
        body = await self._request("GET", USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        sub = body.get("sub")
        if not isinstance(sub, str) or not sub.strip() or len(sub) > MAX_SUB_CHARS:
            raise UpstreamError("Google không trả thông tin người dùng hợp lệ.")
        name = body.get("name")
        return sub, name.strip()[:80] if isinstance(name, str) and name.strip() else None

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=TIMEOUT_SECONDS, transport=self.transport, follow_redirects=False
            ) as client:
                response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Không ghi nội dung phản hồi hay tham số: có thể chứa mã đăng nhập hoặc token
            log.warning("google oauth request failed", extra={"data": {"error": type(exc).__name__}})
            raise UpstreamError("Không kết nối được Google để đăng nhập.") from None
        if not isinstance(body, dict):
            raise UpstreamError("Google trả dữ liệu không hợp lệ.")
        return body
