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
# Trong container mã nằm ở /app/core nên REPO_ROOT là "/": model, dữ liệu và ảnh phải tính từ BACKEND_ROOT (/app)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
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

    # --- Bảo vệ API (TV1): chỉ áp dụng khi CHAT_MODE gọi LLM thật (rag) ---
    api_service_token: SecretStr | None = None  # bot gửi qua X-Service-Token; bỏ trống/"change-me" = chưa cấu hình
    admin_token: SecretStr | None = None  # X-Admin-Token cho /admin/*; bỏ trống/"change-me" = tắt /admin/*
    # --- Đăng nhập Discord OAuth2 (TV1, ADR-005): tắt cho tới khi có đủ client id, client secret và AUTH_SECRET ---
    web_url: str = "http://localhost:15173"  # nơi người dùng được đưa về sau khi đăng nhập
    discord_client_id: str = ""
    discord_client_secret: SecretStr | None = None
    auth_secret: SecretStr | None = None  # khóa băm Discord ID (HMAC), không bao giờ đổi sau khi đã có người dùng
    auth_redirect_uri: str = ""  # bỏ trống: <WEB_URL>/api/v1/auth/discord/callback; phải khớp Discord Developer Portal
    auth_session_days: int = Field(default=7, ge=1, le=90)
    auth_cookie_secure: bool | None = None  # bỏ trống: bật khi WEB_URL là https
    auth_admin_discord_ids: Annotated[list[str], NoDecode] = []  # .env: Discord ID, phân cách bằng dấu phẩy
    rate_limit_per_minute: int = Field(default=10, ge=1, le=1000)  # mỗi IP (web) hoặc mỗi external_ref (bot)
    rate_limit_guild_per_minute: int = Field(default=30, ge=1, le=10000)  # mỗi server Discord (bot gửi guild_id)
    chat_timeout_seconds: float = Field(default=45, gt=0)  # hạn cho một câu hỏi; phải nhỏ hơn timeout 60 s của bot
    # Hạn riêng của SSE web (tính cả chờ token đầu); web không có giới hạn 60 s như bot. JSON/Discord giữ 45 s.
    chat_stream_timeout_seconds: float = Field(default=90, gt=0, le=300)
    # Ngân sách chuẩn bị (Agent + công cụ) trong một lượt; phần còn lại dành cho sinh câu trả lời.
    chat_prepare_timeout_seconds: float = Field(default=25, gt=0, le=120)

    # --- Chat/RAG (TV3): mock mặc định để giữ hợp đồng thử giao diện ---
    chat_mode: Literal["mock", "rag"] = "mock"
    chat_clarification_max_rounds: int | None = Field(default=3, ge=1)
    chat_agent_timeout_seconds: float = Field(default=12, gt=0, le=30)
    chat_agent_max_calls: int | None = Field(default=6, ge=1, le=8)
    # Thử nghiệm (23/11): bật thinking cho các lượt Agent; lượt finish bắt buộc vẫn tắt. Mặc định tắt.
    chat_agent_thinking: bool = False
    # Web auto: ngân sách lượt gọi mô hình của vòng lặp Agent.
    chat_coverage_max_calls: int = Field(default=12, ge=2, le=24)
    chat_persistence: Literal["memory", "postgres"] = "memory"
    chat_memory_collection: str = "conversation_memories"
    chat_memory_candidates: int = Field(default=6, ge=1, le=12)
    chat_memory_timeout_seconds: float = Field(default=5, gt=0, le=15)
    chat_history_messages: int = Field(default=8, ge=0, le=32)
    chat_history_chars: int = Field(default=8000, ge=0, le=32000)
    rag_collection: str = "lore_chunks"
    rag_corpus_policy: Literal["reviewed", "pilot"] = "pilot"
    rag_languages: Annotated[list[str], NoDecode] = ["en"]
    rag_prefetch: int = Field(default=30, ge=5, le=200)
    rag_top_k: int = Field(default=5, ge=1, le=5)
    rag_context_chars: int = Field(default=12000, ge=256, le=64000)
    rag_retrieval_timeout_seconds: float = Field(default=20, gt=0, le=120)
    # Chỉ để đo ablation (24/11): "hybrid" = E5 + BM25 gộp RRF (chạy thật); "dense" = E5-only; "bm25" = BM25-only.
    rag_retrieval_mode: Literal["hybrid", "dense", "bm25"] = "hybrid"
    # Jina reranker chỉ khả dụng khi bật cờ và có API key thật; thiếu key thì runtime dùng NoReranker.
    rag_reranker_enabled: bool = False
    jina_api_key: SecretStr | None = None
    rag_reranker_model: str = Field(default="jina-reranker-v2-base-multilingual", min_length=1)
    rag_reranker_timeout_seconds: float = Field(default=3, gt=0, le=10)
    rag_reranker_max_candidates: int = Field(default=30, ge=2, le=200)
    # Hạn mức token/phút của key Jina (gói free 100k). Gần chạm thì chờ tối đa max_wait giây rồi mới gọi; chờ lâu
    # hơn thì giữ thứ tự RRF thay vì để Jina trả 429. 0 = không tự giới hạn.
    rag_reranker_tokens_per_minute: int = Field(default=100_000, ge=0)
    rag_reranker_max_wait_seconds: float = Field(default=5, ge=0, le=60)
    # local: cross-encoder chạy trên máy (FastEmbed, tải vào rag_models_dir), không cần JINA_API_KEY; jina: gọi API.
    # MiniLM-L12 (120 MB, Apache-2.0, đo 24/11: Recall@5 83,1% -> 86,6%, ~0,75 s/lượt CPU, +0,35 GB RAM). Model
    # train tiếng Anh, hợp vì corpus và truy vấn Agent gửi đi đều tiếng Anh.
    rag_reranker_provider: Literal["jina", "local"] = "jina"
    rag_reranker_local_model: str = Field(default="Xenova/ms-marco-MiniLM-L-12-v2", min_length=1)
    rag_reranker_local_threads: int = Field(default=2, ge=1, le=16)
    rag_reranker_local_max_candidates: int = Field(default=20, ge=2, le=50)
    rag_reranker_local_max_chars: int = Field(default=600, ge=100, le=2000)
    rag_reranker_local_batch_size: int = Field(default=8, ge=1, le=32)
    rag_thinking_enabled: bool = False
    # One additional generation on malformed/blank RAG output, not a grounding bypass.
    rag_format_retries: int = Field(default=1, ge=0, le=1)
    rag_models_dir: str = "models/fastembed"
    rag_batch_size: int = Field(default=32, ge=1, le=128)
    rag_encoder_threads: int = Field(default=2, ge=1, le=32)
    rag_images_enabled: bool = True
    rag_images_catalog: str = "data/delivery/final/clean/images.csv"
    rag_images_documents: str = "data/chunk_runs/s2-full-v1/documents.jsonl"
    rag_images_root: str = "data/media/blobs"
    rag_images_manifests: str = "data/crawl_runs/s2-full-20261028/media"
    rag_images_max_bytes: int = Field(default=20000000, ge=1, le=20000000)
    rag_images_max_pixels: int = Field(default=40000000, ge=1, le=40000000)

    # Available automatically when a key is configured; UI selects auto/always per request.
    tavily_api_key: SecretStr | None = None
    web_search_enabled: bool = True
    web_search_mode: Literal["off", "auto", "always"] = "auto"
    web_search_timeout_seconds: float = Field(default=8, gt=0, le=20)
    web_search_max_results: int = Field(default=3, ge=1, le=5)
    web_search_domains_mode: Literal["prefer", "restrict"] = "prefer"
    web_search_domains: Annotated[list[str], NoDecode] = [
        "eldenring.wiki.gg",
        "eldenring.wiki.fextralife.com",
        "en.bandainamcoent.eu",
    ]

    @field_validator("web_search_domains", mode="before")
    @classmethod
    def _web_domains(cls, value):
        import re

        items = value.split(",") if isinstance(value, str) else value
        result = [item.strip().lower() for item in items]
        if not result or any(not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", item) for item in result):
            raise ValueError("Invalid web search domains")
        return list(dict.fromkeys(result))

    @property
    def auth_enabled(self) -> bool:
        """Đăng nhập chỉ bật khi đủ ba giá trị thật (không trống, không "change-me"), AUTH_SECRET từ 32 ký tự."""

        def real(value: object) -> bool:
            text = value.get_secret_value() if isinstance(value, SecretStr) else (value or "")
            return bool(text.strip()) and text.strip() != PLACEHOLDER

        long_secret = self.auth_secret is not None and len(self.auth_secret.get_secret_value().strip()) >= 32
        return (
            real(self.discord_client_id) and real(self.discord_client_secret) and real(self.auth_secret) and long_secret
        )

    @property
    def auth_callback_url(self) -> str:
        return self.auth_redirect_uri.strip() or f"{self.web_url.rstrip('/')}/api/v1/auth/discord/callback"

    @property
    def auth_cookie_is_secure(self) -> bool:
        return self.web_url.startswith("https://") if self.auth_cookie_secure is None else self.auth_cookie_secure

    @property
    def admin_enabled(self) -> bool:
        """/admin/* chỉ bật khi ADMIN_TOKEN là một giá trị thật (không trống, không "change-me")."""
        secret = self.admin_token.get_secret_value().strip() if self.admin_token else ""
        return bool(secret) and secret != PLACEHOLDER

    @property
    def web_search_available(self) -> bool:
        return bool(
            self.web_search_enabled
            and self.chat_mode == "rag"
            and self.tavily_api_key
            and self.tavily_api_key.get_secret_value().strip()
        )

    @property
    def prepare_budget_seconds(self) -> float:
        """Preparation never takes more than half of a short turn, so generation always keeps time."""
        return min(
            self.chat_prepare_timeout_seconds, max(self.chat_timeout_seconds / 2, self.chat_timeout_seconds - 20)
        )

    @property
    def reranker_available(self) -> bool:
        if self.rag_reranker_provider == "local":
            return self.rag_reranker_enabled
        secret = self.jina_api_key.get_secret_value().strip() if self.jina_api_key else ""
        return self.rag_reranker_enabled and bool(secret) and secret != PLACEHOLDER

    @field_validator("jina_api_key", mode="before")
    @classmethod
    def _blank_jina_key_is_absent(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("rag_languages", mode="before")
    @classmethod
    def _languages(cls, value):
        from core.corpus import parse_languages

        return list(parse_languages(value))

    # --- HTTP ---
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:15173"]  # .env: phân cách bằng dấu phẩy

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("auth_cookie_secure", mode="before")
    @classmethod
    def _empty_cookie_secure_is_auto(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value  # docker compose truyền chuỗi rỗng

    @field_validator("auth_admin_discord_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: object) -> object:
        ids = [i.strip() for i in value.split(",") if i.strip()] if isinstance(value, str) else value
        if isinstance(ids, list) and not all(isinstance(i, str) and i.isdigit() for i in ids):
            raise ValueError("AUTH_ADMIN_DISCORD_IDS chỉ gồm Discord ID (số), phân cách bằng dấu phẩy")
        return ids

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
    if settings.auth_enabled and not settings.auth_cookie_is_secure:
        raise UnsafeConfigError(
            "ENVIRONMENT=prod bật đăng nhập nhưng cookie phiên không có cờ Secure: đặt WEB_URL https://..."
        )


def _reveal(value: object) -> object:
    return value.get_secret_value() if isinstance(value, SecretStr) else value


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    ensure_safe_for_environment(settings)
    return settings
