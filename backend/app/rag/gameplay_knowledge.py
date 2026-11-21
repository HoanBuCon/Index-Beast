"""Ảnh chụp nguồn nhỏ, minh bạch; không vector, không model, không ghi qua mạng."""

import copy
import json
from functools import lru_cache
from pathlib import Path

PACK = Path(__file__).parent / "knowledge/gameplay.json"


@lru_cache(maxsize=1)
def load_pack():
    return json.loads(PACK.read_text(encoding="utf-8"))


def level_rule():
    """Quy tắc tính level đã tuyển chọn (tổng chỉ số = level + 79) lấy từ pack, ở dạng hit có thể trích dẫn."""
    from core.types import Hit

    for group in load_pack()["groups"]:
        for row in group["hits"]:
            if row["payload"].get("rule_kind") == "level_rule":
                return Hit(row["id"], 0.0, copy.deepcopy(row["payload"]))
    raise RuntimeError("Knowledge pack lacks the level accounting rule")
