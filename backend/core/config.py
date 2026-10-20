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

    # Địa chỉ dùng IP: Windows phân giải "localhost" sang IPv6 trước. Cổng mặc định là cổng dev trên máy
    # (cổng gốc + 10000, xem docs/quy_uoc.md); trong Docker, compose đặt tên service và cổng nội bộ.

    # --- PostgreSQL: ghép thành database_url, không khai báo mật khẩu ở hai nơi ---
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=15432, gt=0, lt=65536)
    postgres_user: str = "indexbeast"
    postgres_password: SecretStr = SecretStr(PLACEHOLDER)
    postgres_db: str = "indexbeast"

    # --- Qdrant, Redis ---
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = Field(default=16333, gt=0, lt=65536)
    redis_host: str = "127.0.0.1"
    redis_port: int = Field(default=16379, gt=0, lt=65536)
    redis_db: int = Field(default=0, ge=0)

    # --- Timeout ---
    client_timeout_seconds: float = Field(default=5.0, gt=0)  # kết nối/đọc tới PostgreSQL, Qdrant, Redis
    health_timeout_seconds: float = Field(default=2.0, gt=0)  # tối đa cho mỗi health check

    # --- DeepSeek Platform (TV3): dùng chung cho generation và query rewriting ---
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model: str = Field(default="deepseek-flash", min_length=1)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_tokens: int = Field(default=2048, ge=1, le=8192)
    llm_timeout_seconds: float = Field(default=60, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # --- HTTP ---
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:15173"]  # .env: phân cách bằng dấu phẩy

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
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

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
