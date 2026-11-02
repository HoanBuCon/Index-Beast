"""Atomic artifacts. Raw and media bytes stay outside Git."""

import hashlib
import json
import os
from datetime import UTC, datetime


def now():
    return datetime.now(UTC).isoformat()


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def write_bytes(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(value)
    os.replace(temporary, path)


def save(path, value):
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))
