"""`.env.example` là hợp đồng cấu hình: mọi trường của Settings phải có dòng mẫu, và không dòng nào có chú thích
cuối dòng (docker compose đọc phần chú thích thành giá trị khi giá trị để trống)."""

import re

from core.config import REPO_ROOT, Settings

EXAMPLE = REPO_ROOT / ".env.example"
ASSIGNMENT = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=(.*)$")


def _lines() -> list[str]:
    return EXAMPLE.read_text(encoding="utf-8").splitlines()


def test_every_setting_has_an_example_line():
    documented = {m.group(1) for line in _lines() if (m := ASSIGNMENT.match(line))}
    missing = {name.upper() for name in Settings.model_fields} - documented

    assert not missing, f"thêm vào .env.example: {sorted(missing)}"


def test_no_inline_comments():
    offending = [line for line in _lines() if not line.lstrip().startswith("#") and re.search(r"=.*\s#", line)]

    assert not offending, f"đưa chú thích lên dòng riêng: {offending}"
