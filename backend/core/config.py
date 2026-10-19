"""Settings đọc từ biến môi trường / .env (pydantic-settings). Mọi tham số (top-k, ngưỡng, model, URL) khai báo ở
đây, không hardcode. Mỗi sprint chỉ thêm trường mình cần; đặt theo nhóm và ghi chú ngắn.

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Tìm .env ở backend/ trước, rồi ở thư mục gốc repo; biến môi trường thật luôn được ưu tiên
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    # --- Chung ---
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    # --- Hạ tầng ---
    database_url: str = "postgresql+asyncpg://indexbeast:change-me@127.0.0.1:5432/indexbeast"
    qdrant_url: str = "http://127.0.0.1:6333"
    redis_url: str = "redis://127.0.0.1:6379/0"
    health_timeout_seconds: float = 2.0

    # --- HTTP ---
    cors_origins: str = "http://localhost:5173"  # nhiều origin: phân cách bằng dấu phẩy

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
