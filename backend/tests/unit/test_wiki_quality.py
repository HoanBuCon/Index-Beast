import pytest

from core.text.quest_stages import stage_locations
from ingest.chunk.full import build_chunks
from ingest.chunk.load_full import validate_document
from ingest.transform.wiki_quality import spoiler, wiki_context
from tests.unit.test_full_chunk import fixture


def test_spoiler_labels_are_conservative():
    doc = {"title": "Samurai", "release_scope": "unknown"}
    doc.update(wiki_context({"categories": ["Origins", "Origins_and_Player_Characters"]}, doc))
    intro = {"section": "Introduction"}
    unit = {"text": "Samurai is one of the starting origins in ELDEN RING (2022).", "lang": "en"}
    assert spoiler(doc, intro, unit)[0] == 0
    assert spoiler(doc, intro, {**unit, "lang": "ja"})[0] == 1
    assert spoiler(doc, intro, {**unit, "text": unit["text"] + " Travel to Enir-Ilim."})[0] == 2
    assert spoiler(doc, {"section": "Endings"}, unit)[0] == 2
    assert spoiler({**doc, "release_scope": "sote_candidate"}, intro, unit)[0] == 1
    assert wiki_context({"categories": []}, {"title": "Elden Ring: Nightreign"})["game_scope"] == "out_of_scope"
    assert (
        wiki_context({"categories": []}, {"title": "Nightreign mentions in Elden Ring"})["game_scope"] == "elden_ring"
    )


def test_source_quest_stage_boundary_keeps_evidence_and_splits_ending():
    html = """
    <div class="mw-parser-output">
    <p>Complete this quest to unlock the Age of the Stars ending.</p>
    <ul><li><a href="/wiki/Nokron">Nokron</a></li></ul>
    <ol><li>Defeat Radahn to reach the chest with the Fingerslayer Blade.</li></ol>
    <ul><li><a href="/wiki/Capital">Leyndell, Ashen Capital</a></li></ul>
    <ol><li>Summon Ranni after the final boss.</li></ol>
    </div>
    """
    stages = stage_locations(html)
    assert stages == {"dom:2:li", "dom:7:li"}
    doc, tok = fixture()
    doc["title"] = "Ranni the Witch"
    doc["release_scope"] = "base_candidate"
    doc.update(wiki_context({"categories": ["NPC"]}, doc))
    texts = [
        "Complete this quest to unlock the Age of the Stars ending.",
        "Nokron",
        "Defeat Radahn to reach the chest with the Fingerslayer Blade.",
        "Leyndell, Ashen Capital",
        "Summon Ranni after the final boss.",
    ]
    section = doc["sections"][0]
    section.update(
        section="Questline Progression",
        lang="en",
        text="\n".join(texts),
        blocks=[
            {"kind": "prose", "text": text, "location": location, "notes": []}
            for text, location in zip(texts, ["dom:0:p", "dom:2:li", "dom:5:li", "dom:7:li", "dom:10:li"], strict=True)
        ],
    )
    rows, review, coverage = build_chunks(doc, tok, stages=stages)
    assert not review and len(coverage) == len(rows) == 3
    assert [row["spoiler_level"] for row in rows] == [2, 1, 2]
    assert rows[1]["quest_stage"] == "Nokron"
    assert rows[1]["source_locations"] == ["dom:2:li", "dom:5:li"]
    assert "\n".join(row["text"] for row in rows) == section["text"]


def test_preflight_validates_spoiler_payload():
    doc, tok = fixture()
    doc.update(release_scope="unknown")
    doc.update(wiki_context({"categories": []}, doc))
    rows, _, _ = build_chunks(doc, tok)
    doc["spoiler_level"] = 1
    validate_document(doc, rows, 450)
    rows[-1]["spoiler_level"] = True
    with pytest.raises(ValueError, match="Invalid spoiler metadata"):
        validate_document(doc, rows, 450)
