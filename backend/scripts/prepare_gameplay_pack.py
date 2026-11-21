"""Soạn pack local: chunk nguồn và các trường đã kiểm, không ghi dữ liệu gốc/index.

`--rules-only` làm mới ảnh chụp rule đã tuyển chọn trong pack hiện có mà không cần artifact chunk.
"""

import hashlib
import json
import sys

from app.rag.gameplay_knowledge import PACK
from core.config import REPO_ROOT
from core.types import ChunkRecord

RULE_ALIASES = [
    "stat allocation",
    "stat spread",
    "exact stats",
    "chia chỉ số",
    "phân bổ",
    "cong diem",
    "cộng điểm",
    "attribute",
    "tổng",
]

# (title, url, text, rule_kind, checked).
RULES = [
    (
        "Attribute point accounting",
        "https://eldenring.wikidot.com/stats",
        (
            "A character's level equals the sum of the eight primary attributes minus 79. Thus the "
            "target attribute sum is level + 79. Vigor affects HP; Mind affects FP; Endurance affects "
            "stamina and equip load. Arithmetic does not establish optimality."
        ),
        "level_rule",
        "2026-11-05",
    ),
    # Chỉ số class khởi đầu không còn tuyển chọn ở đây: cả mười trang origin đã có trong corpus (bổ sung S5, 20/11/2026)
    # và agent tự trích Infobox của class.
    (
        "Moonveil requirements",
        "https://eldenring.wiki.gg/wiki/Moonveil",
        (
            "Moonveil's listed one-handed requirements are Strength 12, Dexterity 18 and Intelligence "
            "23. Requirements are distinct from scaling, recommended stats and damage; this does not "
            "establish latest-patch damage."
        ),
        "weapon_rule",
        "2026-11-05",
    ),
    (
        "Respec baseline constraints",
        "https://eip.gg/elden-ring/guides/how-to-respec/",
        (
            "Respec redistributes available attributes without lowering character level. Attributes "
            "determined by the starting class cannot be reduced below their original values. All "
            "available attribute points must be spent."
        ),
        "respec_rule",
        "2026-11-05",
    ),
]


def curated_rule_hits() -> list[dict]:
    hits = []
    for title, url, text, kind, checked in RULES:
        payload = dict(
            text=text,
            title=title,
            section="Verified fields / arithmetic constraints",
            url=url,
            source="curated_gameplay_snapshot",
            source_type="wiki_prose",
            source_type_evidence=f"manual_field_check_{checked}_not_cross_review",
            game_scope="elden_ring",
            release_scope="base",
            patch_version="unknown",
            lang="en",
            review_status="pending",
            rule_kind=kind,
            image_ids=[],
        )
        point_id = "curated:" + hashlib.sha256((url + text).encode()).hexdigest()
        hits.append(dict(id=point_id, payload=payload, text_sha256=hashlib.sha256(text.encode()).hexdigest()))
    return hits


def with_rules(groups: list[dict], rule_hits: list[dict]) -> list[dict]:
    """Các nhóm corpus, rồi ảnh chụp yêu cầu chỉ số của Moonveil và nhóm rule dùng chung."""
    moonveil = next(h for h in rule_hits if h["payload"]["rule_kind"] == "weapon_rule")
    return [*groups, {"aliases": ["Moonveil"], "hits": [moonveil]}, {"aliases": RULE_ALIASES, "hits": rule_hits}]


def write(pack: dict) -> None:
    PACK.parent.mkdir(parents=True, exist_ok=True)
    # Ghi byte, không dùng write_text: giữ xuống dòng LF cả trên Windows.
    PACK.write_bytes((json.dumps(pack, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def refresh_rules() -> None:
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    corpus = [g for g in pack["groups"] if not any(h["id"].startswith("curated:") for h in g["hits"])]
    pack["groups"] = with_rules(corpus, curated_rule_hits())
    write(pack)
    print("Refreshed curated rules; groups:", len(pack["groups"]))


def main():
    path = REPO_ROOT / "backend/data/chunk_runs/s2-full-v1/chunks.jsonl"
    records = [json.loads(line) for line in path.open(encoding="utf-8")]
    groups = []
    definitions = [
        (
            ["Ranni", "Nokron", "Fingerslayer Blade", "Renna's Rise", "Moonlight Altar"],
            "Ranni the Witch",
            ["Questline Progression"],
        ),
        (["Academy Glintstone Key", "Thops"], "Academy Glintstone Key", ["Description", "Use"]),
        (["Morgott"], "Morgott, the Omen King", ["Introduction"]),
        (["Fire Giant"], "Fire Giant", ["Introduction"]),
        (["Maliketh"], "Maliketh, the Black Blade", ["Introduction"]),
        (["Moonveil"], "Moonveil", ["Notes"]),
    ]
    for aliases, title, sections in definitions:
        hits = []
        for row in records:
            if (
                row["title"] == title
                and row["section"] in sections
                and row["lang"] == "en"
                and row["source_type"] == "wiki_prose"
            ):
                record = ChunkRecord.model_validate(row)
                hits.append(
                    {
                        "id": str(record.point_uuid),
                        "payload": record.payload(),
                        "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                    }
                )
        groups.append({"aliases": aliases, "hits": hits})
    write(
        {
            "version": 1,
            "review_status": "pending",
            "artifact": str(path.relative_to(REPO_ROOT)),
            "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "notice": (
                "AI-assisted snapshots, technically usable in pilot; not cross-reviewed or current-patch certification."
            ),
            "groups": with_rules(groups, curated_rule_hits()),
        }
    )
    print("Wrote gameplay pack groups:", len(groups) + 2)


if __name__ == "__main__":
    refresh_rules() if "--rules-only" in sys.argv[1:] else main()
