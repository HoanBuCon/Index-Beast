"""Small transparent source snapshots; no vectors, models or network writes."""

import json
from functools import lru_cache
from pathlib import Path

PACK = Path(__file__).parent / "knowledge/gameplay.json"


@lru_cache(maxsize=1)
def load_pack():
    return json.loads(PACK.read_text(encoding="utf-8"))
