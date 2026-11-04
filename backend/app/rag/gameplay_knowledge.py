"""Small transparent source snapshots; no vectors, models or network writes."""

import json
import re
from functools import lru_cache
from pathlib import Path

from app.rag.overview import folded
from core.types import Hit

PACK = Path(__file__).parent / "knowledge/gameplay.json"


@lru_cache(maxsize=1)
def load_pack():
    return json.loads(PACK.read_text(encoding="utf-8"))


def supplements(query, policy, spoilers):
    from app.rag.build_math import arithmetic_only

    if not re.search(
        (
            "quest|route|walkthrough|progress|nhiem vu|lo trinh|di dau|build|require|chi "
            "so|intelligence|stat|key|chia|phan bo|caria|nokron|ainsel|moonlight|seluvis|attribute|tong"
        ),
        folded(query),
    ):
        return []
    result, seen = [], set()
    for group in load_pack()["groups"]:
        if any(alias.casefold() in query.casefold() for alias in group["aliases"]):
            for row in group["hits"]:
                if arithmetic_only(query) and row["payload"].get("rule_kind") not in {None, "level_rule"}:
                    continue
                if row["id"] not in seen and policy.exclusion_reason(row["payload"], spoilers=spoilers) is None:
                    seen.add(row["id"])
                    result.append(
                        Hit(row["id"], 0.0, {**row["payload"], "local_candidate_origin": "curated_source_snapshot"})
                    )
    return result


def trusted_rule_kind(hit):
    for group in load_pack()["groups"]:
        for row in group["hits"]:
            if row["id"] == hit.id and row["payload"] == {
                k: v for k, v in hit.payload.items() if k != "local_candidate_origin"
            }:
                return row["payload"].get("rule_kind")
    return None
