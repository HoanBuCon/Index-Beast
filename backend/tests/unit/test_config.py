from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import create_app
from core.config import ENV_FILE, REPO_ROOT, Settings, UnsafeConfigError, ensure_safe_for_environment


def make(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_env_file_is_repo_root_regardless_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert ENV_FILE == REPO_ROOT / ".env"
    assert (REPO_ROOT / "backend" / "core" / "config.py").is_file()
    assert Path(Settings.model_config["env_file"]).is_absolute()


def test_real_env_var_overrides_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=WARNING\nPOSTGRES_DB=from_file  # chú thích cuối dòng\n", encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "ERROR"
    assert settings.postgres_db == "from_file"


def test_database_url_escapes_special_characters():
    url = make(postgres_password="p@ss:/word", postgres_host="postgres").database_url

    assert url == "postgresql+asyncpg://indexbeast:p%40ss%3A%2Fword@postgres:15432/indexbeast"


def test_cors_origins_accept_comma_separated_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, https://b.test,")

    assert make().cors_origins == ["http://a.test", "https://b.test"]


def test_log_level_is_case_insensitive_and_validated():
    assert make(log_level="debug").log_level == "DEBUG"
    with pytest.raises(ValidationError):
        make(log_level="verbose")


def test_timeouts_must_be_positive():
    with pytest.raises(ValidationError):
        make(health_timeout_seconds=0)


def test_prod_refuses_placeholder_secrets_without_leaking_values():
    settings = make(environment="prod", qdrant_host="real-host")

    with pytest.raises(UnsafeConfigError, match="POSTGRES_PASSWORD") as err:
        ensure_safe_for_environment(settings)
    assert "real-host" not in str(err.value)


def test_prod_accepts_real_secrets_and_dev_accepts_placeholders():
    ensure_safe_for_environment(make(environment="prod", postgres_password="s3cret"))
    ensure_safe_for_environment(make(environment="dev"))


def test_secret_is_hidden_in_repr():
    assert "s3cret" not in repr(make(postgres_password="s3cret"))


def test_create_app_refuses_unsafe_prod_config(ctx):
    with pytest.raises(UnsafeConfigError):
        create_app(make(environment="prod"), context=ctx)


def test_service_urls_are_built_from_host_and_port():
    settings = make(qdrant_host="qdrant", qdrant_port=6333, redis_host="redis", redis_port=6379, redis_db=2)

    assert settings.qdrant_url == "http://qdrant:6333"
    assert settings.redis_url == "redis://redis:6379/2"
