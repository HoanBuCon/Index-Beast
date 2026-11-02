"""Quy ước cổng (docs/quy_uoc.md §8): không tiến trình nào của dự án dùng cổng mặc định của công cụ.

Ngoại lệ: Caddy 80/443 trên VPS; PostgreSQL/Redis/Qdrant giữ cổng gốc bên trong mạng Docker (vế phải của
`ports:` trong compose, và giá trị compose truyền cho container api).
"""

import re

from core.config import REPO_ROOT, Settings

DEFAULT_PORTS = {
    3000,  # Node/React dev
    4173,  # vite preview
    5000,  # Flask
    5173,  # Vite
    5432,  # PostgreSQL
    6333,  # Qdrant HTTP
    6334,  # Qdrant gRPC
    6379,  # Redis
    8000,  # uvicorn
    8080,  # HTTP thay thế
}
PUBLIC_HTTP_PORTS = {80, 443}  # chỉ Caddy


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _active_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def test_env_example_uses_project_ports():
    lines = _active_lines(_read(".env.example"))
    ports = {int(m.group(1)) for line in lines if (m := re.match(r"^\w*_PORT=(\d+)$", line.strip()))}
    ports |= {int(p) for line in lines for p in re.findall(r"://[^/:\s]+:(\d+)", line)}

    assert ports, "không tìm thấy cổng nào trong .env.example"
    assert not ports & DEFAULT_PORTS, f"cổng mặc định trong .env.example: {sorted(ports & DEFAULT_PORTS)}"


def test_settings_defaults_use_project_ports():
    s = Settings(_env_file=None)
    ports = {s.postgres_port, s.qdrant_port, s.redis_port}
    ports |= {int(p) for origin in s.cors_origins for p in re.findall(r":(\d+)$", origin)}

    assert not ports & DEFAULT_PORTS, f"cổng mặc định trong core/config.py: {sorted(ports & DEFAULT_PORTS)}"


def test_compose_publishes_only_project_ports_on_the_host():
    published: set[int] = set()
    for host_side in re.findall(r'"(?:127\.0\.0\.1:)?(\$\{\w+:-\d+\}|\d+):\d+"', _read("docker-compose.yml")):
        fallback = re.fullmatch(r"\$\{\w+:-(\d+)\}", host_side)
        published.add(int(fallback.group(1) if fallback else host_side))

    assert not published & DEFAULT_PORTS, f"compose mở cổng mặc định ra máy: {sorted(published & DEFAULT_PORTS)}"
    assert published - PUBLIC_HTTP_PORTS, "compose phải publish cổng dev"


def test_api_process_never_listens_on_default_port():
    sources = {
        "backend/Dockerfile": r'"--port", "(\d+)"|EXPOSE (\d+)',
        "infra/Caddyfile": r"reverse_proxy api:(\d+)",
        "Makefile": r"\),(\d+)\)",
        "web/vite.config.ts": r'DEFAULT_\w+_PORT = "(\d+)"',
        "docker-compose.yml": r"api:(\d+)|127\.0\.0\.1:(\d+)/api",
    }
    for path, pattern in sources.items():
        ports = {int(group) for m in re.finditer(pattern, _read(path)) for group in m.groups() if group}
        assert ports, f"không tìm thấy cổng trong {path}"
        assert not ports & DEFAULT_PORTS, f"{path} dùng cổng mặc định: {sorted(ports & DEFAULT_PORTS)}"
