"""Xuất hợp đồng API v1 ra docs/api/openapi.json (web/bot đọc file này để viết type).

Chạy từ backend/: python -m scripts.export_openapi          # ghi file
                  python -m scripts.export_openapi --check  # exit 1 nếu file lệch code (dùng trong CI)

Phụ trách: TV1 · [S2] API contract v1
"""

import json
import sys
from pathlib import Path

from app.main import create_app
from core.config import Settings

TARGET = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


def build_spec() -> str:
    settings = Settings(_env_file=None, environment="test")  # test: bật OpenAPI, không đọc .env của máy dev
    spec = create_app(settings).openapi()
    # /dev/* chỉ có ở dev, không thuộc hợp đồng v1
    spec["paths"] = {p: v for p, v in spec["paths"].items() if "/dev/" not in p}
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    spec = build_spec()
    if "--check" in sys.argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != spec:
            print("docs/api/openapi.json is stale: run `python -m scripts.export_openapi` and commit.")
            return 1
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(spec, encoding="utf-8", newline="\n")
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
