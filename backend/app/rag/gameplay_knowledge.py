"""Small transparent source snapshots; no vectors, models or network writes."""

import copy
import json
from functools import lru_cache
from pathlib import Path

PACK = Path(__file__).parent / "knowledge/gameplay.json"


@lru_cache(maxsize=1)
def load_pack():
    return json.loads(PACK.read_text(encoding="utf-8"))


def level_rule():
    """The curated level accounting rule (attributes total = level + offset) from the pack, as a citable hit."""
    from core.types import Hit

    for group in load_pack()["groups"]:
        for row in group["hits"]:
            if row["payload"].get("rule_kind") == "level_rule" and row["payload"].get("rule_data"):
                return Hit(row["id"], 0.0, copy.deepcopy(row["payload"])), row["payload"]["rule_data"]
    raise RuntimeError("Knowledge pack lacks the level accounting rule")
