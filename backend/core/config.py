"""Cấu hình toàn hệ thống, đọc một lần lúc khởi động (pydantic-settings).

Nguồn, ưu tiên từ cao xuống thấp:
  1. Biến môi trường thật (docker-compose `environment:`, CI, `export` trong shell)
  2. File `.env` ở GỐC repo (đường dẫn tuyệt đối — chạy từ thư mục nào cũng như nhau)
  3. Giá trị mặc định dưới đây (dùng được ngay cho dev local)

Thêm tham số mới: thêm trường vào đúng nhóm + dòng mẫu trong `.env.example`; nếu container cần,
thêm vào `environment:` của service đó trong `docker-compose.yml` (README → "Cấu hình").

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
PLACEHOLDER = "change-me"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # --- Chung ---
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: LogLevel = "INFO"

    # --- PostgreSQL: ghép thành database_url, không khai báo mật khẩu ở hai nơi ---
    postgres_host: str = "127.0.0.1"  # dùng IP: Windows phân giải "localhost" sang IPv6 trước
    postgres_port: int = 5432
    postgres_user: str = "indexbeast"
    postgres_password: SecretStr = SecretStr(PLACEHOLDER)
    postgres_db: str = "indexbeast"

    # --- Qdrant, Redis ---
    qdrant_url: str = "http://127.0.0.1:6333"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- Timeout ---
    client_timeout_seconds: float = Field(default=5.0, gt=0)  # kết nối/đọc tới PostgreSQL, Qdrant, Redis
    health_timeout_seconds: float = Field(default=2.0, gt=0)  # tối đa cho mỗi health check

    # --- HTTP ---
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]  # .env: phân cách bằng dấu phẩy

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        return [o.strip() for o in value.split(",") if o.strip()] if isinstance(value, str) else value

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),  # URL.create tự mã hoá ký tự đặc biệt
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


class UnsafeConfigError(RuntimeError):
    """Cấu hình không an toàn cho môi trường hiện tại."""


def ensure_safe_for_environment(settings: Settings) -> None:
    """Production từ chối khởi động khi còn giá trị mẫu. Chỉ nêu tên biến, không in giá trị ra log."""
    if not settings.is_prod:
        return
    leaked = [name.upper() for name, value in settings if _reveal(value) == PLACEHOLDER]
    if leaked:
        raise UnsafeConfigError(f"ENVIRONMENT=prod nhưng vẫn dùng giá trị mẫu '{PLACEHOLDER}': {', '.join(leaked)}")


def _reveal(value: object) -> object:
    return value.get_secret_value() if isinstance(value, SecretStr) else value


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    ensure_safe_for_environment(settings)
    return settings
