"""Local pack authoring: source chunks and checked fields, no original-data/index writes."""

import hashlib
import json

from app.rag.gameplay_knowledge import PACK
from core.config import REPO_ROOT
from core.types import ChunkRecord


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
    rules = [
        (
            "Attribute point accounting",
            "https://eldenring.wikidot.com/stats",
            (
                "A character's level equals the sum of the eight primary attributes minus 79. Thus the "
                "target attribute sum is level + 79. Vigor affects HP; Mind affects FP; Endurance affects "
                "stamina and equip load. Arithmetic does not establish optimality."
            ),
            "level_rule",
        ),
        (
            "Samurai starting attributes",
            "https://wiki.eso-ui.com/index.php/Elden_Ring:Samurai",
            (
                "Samurai starts at level 9 with Vigor 12, Mind 11, Endurance 13, Strength 12, Dexterity "
                "15, Intelligence 9, Faith 8, Arcane 8. These are starting values, not a recommended final "
                "build."
            ),
            "class_rule",
        ),
        (
            "Moonveil requirements",
            "https://eldenring.wiki.gg/wiki/Moonveil",
            (
                "Moonveil's listed one-handed requirements are Strength 12, Dexterity 18 and Intelligence "
                "23. Requirements are distinct from scaling, recommended stats and damage; this does not "
                "establish latest-patch damage."
            ),
            "weapon_rule",
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
        ),
    ]
    rule_hits = []
    for title, url, text, kind in rules:
        point_id = "curated:" + hashlib.sha256((url + text).encode()).hexdigest()
        payload = dict(
            text=text,
            title=title,
            section="Verified fields / arithmetic constraints",
            url=url,
            source="curated_gameplay_snapshot",
            source_type="wiki_prose",
            source_type_evidence="manual_field_check_2026-11-05_not_cross_review",
            game_scope="elden_ring",
            release_scope="base",
            patch_version="unknown",
            lang="en",
            review_status="pending",
            rule_kind=kind,
            image_ids=[],
        )
        rule_hits.append(dict(id=point_id, payload=payload, text_sha256=hashlib.sha256(text.encode()).hexdigest()))
    groups.append({"aliases": ["Moonveil"], "hits": [rule_hits[2]]})
    groups.append(
        {
            "aliases": [
                "stat allocation",
                "stat spread",
                "exact stats",
                "chia chỉ số",
                "phân bổ",
                "cong diem",
                "cộng điểm",
                "attribute",
                "tổng",
            ],
            "hits": rule_hits,
        }
    )
    PACK.parent.mkdir(parents=True, exist_ok=True)
    PACK.write_text(
        json.dumps(
            {
                "version": 1,
                "review_status": "pending",
                "artifact": str(path.relative_to(REPO_ROOT)),
                "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "notice": (
                    "AI-assisted snapshots, technically usable in pilot; not cross-reviewed or current-patch "
                    "certification."
                ),
                "groups": groups,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Wrote gameplay pack groups:", len(groups))


if __name__ == "__main__":
    main()
