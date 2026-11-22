"""Gọi Discord OAuth2 (authorization code + PKCE, scope `identify`): dựng URL cho người dùng, đổi mã lấy access token,
đọc ID và tên. Chỉ nói chuyện với discord.com; lỗi mạng hoặc dữ liệu lạ trả UpstreamError (502), không lộ chi tiết.

Phụ trách: TV1 · [S4] Auth service (ADR-005)
"""

import logging
from urllib.parse import urlencode

import httpx

from core.config import Settings
from core.errors import UpstreamError

log = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TIMEOUT_SECONDS = 10


class DiscordOAuth:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport  # test thay bằng MockTransport

    def authorize_url(self, state: str, code_challenge: str) -> str:
        query = urlencode(
            {
                "client_id": self.settings.discord_client_id,
                "redirect_uri": self.settings.auth_callback_url,
                "response_type": "code",
                "scope": "identify",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "prompt": "none",
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange(self, code: str, code_verifier: str) -> str:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.auth_callback_url,
            "code_verifier": code_verifier,
        }
        auth = (self.settings.discord_client_id, self.settings.discord_client_secret.get_secret_value())
        body = await self._request("POST", f"{API}/oauth2/token", data=data, auth=auth)
        token = body.get("access_token")
        if not isinstance(token, str) or not token:
            raise UpstreamError("Discord không trả access token hợp lệ.")
        return token

    async def fetch_user(self, access_token: str) -> tuple[str, str | None]:
        """(Discord ID, tên hiển thị). ID là chuỗi số; tên có thể trống."""
        body = await self._request("GET", f"{API}/users/@me", headers={"Authorization": f"Bearer {access_token}"})
        discord_id = body.get("id")
        if not isinstance(discord_id, str) or not discord_id.isdigit():
            raise UpstreamError("Discord không trả thông tin người dùng hợp lệ.")
        name = body.get("global_name") or body.get("username")
        return discord_id, name[:80] if isinstance(name, str) and name.strip() else None

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self.transport) as client:
                response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Không ghi nội dung phản hồi hay URL kèm tham số: có thể chứa mã đăng nhập
            log.warning("discord oauth request failed", extra={"data": {"error": type(exc).__name__}})
            raise UpstreamError("Không kết nối được Discord để đăng nhập.") from None
        if not isinstance(body, dict):
            raise UpstreamError("Discord trả dữ liệu không hợp lệ.")
        return body
