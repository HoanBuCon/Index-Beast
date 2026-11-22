import pytest

from core.ids import document_id
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


def test_tarnished_exclusive_content_is_out_of_scope_but_mentions_and_sote_are_not():
    exclusive_lead = {
        "title": "Idus Sword",
        "content": (
            '<div class="mw-parser-output"><p>This weapon is exclusive to ELDEN RING Tarnished Edition '
            "or to those who purchased the Tarnished Pack DLC.</p></div>"
        ),
        "categories": ["Light_Greatswords"],
    }
    scoped = wiki_context(exclusive_lead, {"title": exclusive_lead["title"]})
    assert scoped["game_scope"] == "out_of_scope"
    assert scoped["game_scope_reason"] == "external_tarnished_edition_content"

    mentions = {
        "title": "A base game weapon",
        "content": (
            '<div class="mw-parser-output"><p>A weapon in Elden Ring.</p>'
            "<p>Trivia: its description changed in the Tarnished Pack DLC. "
            '<a href="/wiki/Tarnished_Pack"><img src="/images/TP.webp"></a></p></div>'
        ),
        "categories": ["Weapons"],
    }
    sote = {
        "title": "Messmer",
        "content": '<div class="mw-parser-output"><p>Messmer appears in Shadow of the Erdtree.</p></div>',
        "categories": ["NPC"],
    }
    assert wiki_context(mentions, {"title": mentions["title"]})["game_scope"] == "elden_ring"
    assert wiki_context(sote, {"title": sote["title"]})["game_scope"] == "elden_ring"
    assert wiki_context({"categories": [], "content": ""}, {"title": "Tarnished Pack"})["game_scope"] == "out_of_scope"


def test_tarnished_pack_infobox_badge_marks_equipment_page_out_of_scope():
    raw = {
        "title": "Silver Grooved Helm",
        "content": (
            '<div class="mw-parser-output"><aside class="portable-infobox">'
            '<img src="/images/thumb/TP.webp/25px-TP.webp"></aside>'
            "<p>The Silver Grooved Helm is an armor piece found in ELDEN RING.</p></div>"
        ),
        "categories": ["Head"],
    }
    assert wiki_context(raw, {"title": raw["title"]})["game_scope"] == "out_of_scope"


def test_tarnished_pack_acquisition_badge_marks_item_but_see_also_badge_does_not():
    acquisition = {
        "title": "Silver Grooved Helm",
        "content": (
            '<div class="mw-parser-output"><p>The Silver Grooved Helm is an armor piece found in ELDEN RING.</p>'
            '<h2><span class="mw-headline" id="Acquisition">Acquisition</span></h2>'
            "<ul><li>Starting armor for Idus Knight "
            '<a href="/wiki/Tarnished_Pack" title="Tarnished Pack">'
            '<img src="/images/thumb/TP.webp/25px-TP.webp"></a></li></ul></div>'
        ),
        "categories": ["Head"],
    }
    cross_link = {
        "title": "Base game article",
        "content": (
            '<div class="mw-parser-output"><h2><span class="mw-headline" id="See_Also">See Also</span></h2>'
            '<ul><li><a href="/wiki/Tarnished_Pack" title="Tarnished Pack">'
            '<img src="/images/thumb/TP.webp/25px-TP.webp"></a></li></ul></div>'
        ),
        "categories": ["Items"],
    }
    assert wiki_context(acquisition, {"title": acquisition["title"]})["game_scope"] == "out_of_scope"
    assert wiki_context(cross_link, {"title": cross_link["title"]})["game_scope"] == "elden_ring"


def test_pack_badge_in_skill_acquisition_does_not_exclude_the_skill_page():
    raw = {
        "title": "Skill: Overhead Stance",
        "content": (
            '<div class="mw-parser-output"><p>Overhead Stance is a skill in ELDEN RING.</p>'
            '<h2><span class="mw-headline" id="Acquisition">Acquisition</span></h2>'
            "<ul><li>Found on the Sword of Night.</li>"
            "<li>Found on a Tarnished Pack weapon "
            '<a href="/wiki/Tarnished_Pack" title="Tarnished Pack">'
            '<img src="/images/thumb/TP.webp/25px-TP.webp"></a></li></ul></div>'
        ),
        "categories": ["Skills"],
    }
    assert wiki_context(raw, {"title": raw["title"]})["game_scope"] == "elden_ring"


def test_pack_badge_applies_to_armor_with_plural_title():
    raw = {
        "categories": ["Arms"],
        "content": (
            "<p>The Silver Grooved Gauntlets are an armor piece found in ELDEN RING.</p>"
            '<h2><span class="mw-headline" id="Acquisition">Acquisition</span></h2>'
            '<ul><li>Starting armor <a title="Tarnished Pack"><img src="/images/TP.webp"></a></li></ul>'
        ),
    }
    assert wiki_context(raw, {"title": "Silver Grooved Gauntlets"})["game_scope"] == "out_of_scope"


def test_tarnished_edition_release_explicitly_applies_to_item_in_lead():
    raw = {
        "categories": ["Items"],
        "content": "<p>Regalia is a Key Item in ELDEN RING. It was introduced with ELDEN RING Tarnished Edition.</p>",
    }
    assert wiki_context(raw, {"title": "Spectral Steed Regalia: Tree Sentinel"})["game_scope"] == "out_of_scope"


def test_tarnished_badge_in_exclusive_skill_lead_applies_to_the_skill():
    raw = {
        "categories": ["Skill", "Unique_Skill"],
        "content": (
            "<p>Muleta is a Skill in ELDEN RING. It is exclusive to Leontiel's Greatsword "
            '<a title="Tarnished Pack"><img src="/images/TP.webp"></a>.</p>'
        ),
    }
    assert wiki_context(raw, {"title": "Unique Skill: Muleta"})["game_scope"] == "out_of_scope"


def test_external_dlc_document_contract_allows_zero_chunks_with_scope_reason():
    doc = {
        "doc_id": str(document_id("wikigg", "34037")),
        "source": "wikigg",
        "source_id": "34037",
        "game_scope": "out_of_scope",
        "game_scope_reason": "external_tarnished_edition_content",
    }
    assert validate_document(doc, [], 450)


def test_external_dlc_page_builds_no_chunks_and_one_review_record():
    doc, tok = fixture()
    doc.update(game_scope="out_of_scope", game_scope_reason="external_tarnished_edition_content")
    chunks, reviews, coverage = build_chunks(doc, tok)
    assert chunks == [] and coverage == []
    assert reviews == [{"reason": "external_tarnished_edition_content", "source_snapshot": "raw.json"}]


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
