"""Small transparent source snapshots; no vectors, models or network writes."""

import json
from functools import lru_cache
from pathlib import Path

PACK = Path(__file__).parent / "knowledge/gameplay.json"


@lru_cache(maxsize=1)
def load_pack():
    return json.loads(PACK.read_text(encoding="utf-8"))


def trusted_rule_kind(hit):
    for group in load_pack()["groups"]:
        for row in group["hits"]:
            if row["id"] == hit.id and row["payload"] == {
                k: v for k, v in hit.payload.items() if k != "local_candidate_origin"
            }:
                return row["payload"].get("rule_kind")
    return None
