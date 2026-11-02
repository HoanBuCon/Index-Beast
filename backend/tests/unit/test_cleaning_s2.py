"""Cleaning regression cases preserve meaning and quarantine uncertainty."""

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.text.html_clean import clean_html
from core.text.normalize import normalize_text
from ingest.artifacts import save, sha256
from ingest.filter.rules import page_evidence, section_decision
from ingest.settings import load_settings
from ingest.transform.document import IMAGES, LORE, REVIEW, csv_write, run_clean, verify_csv


def article(content):
    return '<div class="mw-parser-output" lang="en">' + content + "</div>"


def clean(content):
    return clean_html(article(content), title="NPC", skip_sections=["Gallery", "References"])


def joined(result):
    return "\n".join(x["text"] for x in result["sections"])


def test_dialogue_table_retains_trigger_and_speaker():
    r = clean(
        "<h2>Dialogue</h2><table><tr><th>Speaker</th><th>After giving token</th></tr>"
        "<tr><td>Ranni</td><td>Thou hast done well.<br/>Farewell.</td></tr></table>"
    )
    assert "Speaker | After giving token" in joined(r)
    assert "Ranni | Thou hast done well.\nFarewell." in joined(r)
    assert r["sections"][0]["blocks"][0]["kind"] == "dialogue"


def test_repeated_dialogue_lines_are_not_global_duplicates():
    r = clean("<h2>Dialogue</h2><p>After speaking: Hello.</p><p>After returning: Hello.</p>")
    assert joined(r).count("Hello.") == 2


def test_hidden_dialogue_tab_is_kept():
    assert "Hidden source dialogue" in joined(
        clean('<h2>Dialogue</h2><div style="display:none"><p>Hidden source dialogue</p></div>')
    )


def test_only_proven_display_quote_duplicate_is_removed():
    r = clean(
        '<div class="hidden"><p>Same quote - NPC</p></div>'
        '<div style="display:none"><blockquote class="quote"><p>Same quote - NPC</p></blockquote></div>'
    )
    assert joined(r).count("Same quote") == 1
    assert any(x["reason"] == "duplicate_quote_display_variant" for x in r["removed"])


def test_nonidentical_quote_variants_are_kept():
    r = clean(
        '<div class="hidden"><p>Original quote</p></div>'
        '<div><blockquote class="quote">Different quote</blockquote></div>'
    )
    assert "Original quote" in joined(r) and "Different quote" in joined(r)


def test_stats_table_removed_without_deleting_quest_table():
    r = clean(
        "<h2>Basic Info</h2><table><tr><th>HP</th><th>Runes</th></tr><tr><td>500</td><td>20</td></tr></table>"
        "<h2>Quest Items</h2><table><tr><th>Item</th><th>Requirements</th></tr>"
        "<tr><td>Key</td><td>Help NPC first</td></tr></table>"
    )
    assert "500" not in joined(r) and "Help NPC first" in joined(r)
    assert any(x["reason"] == "numeric_stats_table" for x in r["removed"])


def test_numeric_stats_cells_without_th_are_removed():
    r = clean("<table><tr><td>HP</td><td>Runes</td></tr><tr><td>500</td><td>20</td></tr></table>")
    assert "500" not in joined(r)


def test_infobox_lore_fields_are_retained_and_stats_removed():
    r = clean(
        '<aside class="portable-infobox">'
        '<div class="pi-data" data-source="race"><h3 class="pi-data-label">Race</h3>'
        '<div class="pi-data-value">Living Jar</div></div>'
        '<div class="pi-data" data-source="hp"><h3 class="pi-data-label">HP</h3>'
        '<div class="pi-data-value">500</div></div></aside>'
        "<p>Article introduction.</p>"
    )
    assert "Living Jar" in joined(r) and "500" not in joined(r)
    assert next(x for x in r["sections"] if "Article introduction" in x["text"])["section"] == "Introduction"


def test_nested_headings_keep_parent_scope():
    r = clean("<h2>Shadow of the Erdtree</h2><h3>Dialogue</h3><p>DLC quote</p><h2>Lore</h2><p>Base prose</p>")
    assert r["sections"][0]["section"] == "Shadow of the Erdtree > Dialogue"
    config = load_settings()["clean"]
    assert (
        section_decision(r["sections"][0], {"status": "base", "reason": "test", "quote": ""}, config)[0] == "excluded"
    )


def test_mixed_marker_is_reviewed_instead_of_whole_page_promotion():
    config = load_settings()["clean"]
    s = {"section": "Background", "text": "The base history connects with Messmer.", "kind": "article", "blocks": []}
    assert section_decision(s, {"status": "base", "reason": "anchor", "quote": "Limgrave"}, config)[0] == "review"


def test_unknown_scope_never_promotes_from_sample_membership():
    config = load_settings()["clean"]
    raw = {"content": article("<p>A mysterious being.</p>"), "game_scope": None}
    page = page_evidence(raw, config)
    s = {"section": "Lore", "text": "A mysterious being.", "kind": "article", "blocks": []}
    assert section_decision(s, page, config)[0] == "review"


def test_explicit_dlc_page_excludes_even_unmarked_subsections():
    config = load_settings()["clean"]
    p = page_evidence({"content": article("<p>This is a boss in Shadow of the Erdtree.</p>")}, config)
    s = {"section": "Notes", "text": "No explicit expansion names here.", "kind": "article", "blocks": []}
    assert section_decision(s, p, config)[0] == "excluded"


def test_ui_stub_and_reference_markers_removed_but_text_retained():
    r = clean(
        "<nav>Menu noise</nav><div>This page is a <a>stub</a>. You can help by expanding it.</div>"
        '<p>Important lore<sup class="reference">[1]</sup>.</p>'
    )
    assert joined(r) == "Important lore."
    assert {x["reason"] for x in r["removed"]} >= {"interface_or_navigation", "editorial_stub_notice"}


def test_reference_and_gallery_content_audited_with_locator():
    r = clean(
        "<h2>Gallery</h2><p>Image caption.</p><h2>References</h2><p>Source quotation.</p><h2>Lore</h2><p>Keep.</p>"
    )
    assert joined(r) == "Keep."
    assert all(x["location"].startswith("dom:") for x in r["removed"])
    assert "Source quotation." in [x["text"] for x in r["removed"]]


def test_unicode_and_multiline_not_translated():
    assert normalize_text('Cafe\u0301\xa0  "item",\n 日本語  ') == 'Café "item",\n日本語'


def test_item_description_is_retained():
    assert "Work of a wandering artist." in joined(clean("<h2>Description</h2><p>Work of a wandering artist.</p>"))


def test_combat_equipment_removed_and_material_conditions_kept():
    r = clean(
        "<h2>Equipment</h2><table><tr><th>Right Hand</th><th>Left Hand</th></tr>"
        "<tr><td>Sword</td><td>Shield</td></tr></table>"
        "<h2>Acquisition</h2><p>Give the shield after the quest.</p>"
    )
    assert "Sword" not in joined(r) and "after the quest" in joined(r)


def test_placeholder_removed():
    assert "Please add a quote." not in joined(clean("<p>Please add a quote.</p><p>Lore remains.</p>"))


def test_speculation_not_auto_labeled_in_game():
    from ingest.transform.metadata import section_metadata

    s = {"section": "Notes", "text": "Perhaps this is an allusion.", "blocks": [{"kind": "prose"}]}
    assert section_metadata(s, {}, "en")["source_type"] == "speculation"


def test_bilingual_description_language_and_origin_unknown():
    from ingest.transform.metadata import section_metadata

    s = {"section": "Description", "text": "Item description 日本語", "blocks": [{"kind": "prose"}]}
    assert section_metadata(s, {}, "en") == {"source_type": "unknown", "lang": "unknown"}


def test_csv_roundtrip_commas_quotes_newlines_and_unicode(tmp_path):
    text = 'Café, "quoted"\nTiếng Việt 日本語'
    lore = {k: "" for k in LORE}
    lore.update(record_id="1", text=text, scope_status="base", image_ids="[]", content_hash=sha256(text.encode()))
    expected = {"lore_clean.csv": [lore], "review.csv": [], "images.csv": []}
    for name, headers in [("lore_clean.csv", LORE), ("review.csv", REVIEW), ("images.csv", IMAGES)]:
        csv_write(tmp_path / name, headers, expected[name])
    assert verify_csv(tmp_path, expected)["lore_clean.csv"]["rows"] == 1
    assert (tmp_path / "lore_clean.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def make_sample(root):
    pages = []
    for i in range(200):
        html = article("<p>A place in Limgrave.</p><h2>Lore</h2><p>Local history.</p><h2>Gallery</h2><p>Caption</p>")
        raw = {
            "source": "wikigg",
            "source_id": str(i),
            "revision_id": 1,
            "title": f"Page {i}",
            "content": html,
            "content_hash": sha256(html.encode()),
            "url": f"https://example.org/{i}",
            "fetched_at": "2026-10-28T00:00:00Z",
        }
        save(root / "raw/wikigg" / f"{i}.json", raw)
        save(
            root / "media/manifests/wikigg" / f"{i}.json",
            {
                "revision_id": 1,
                "images": [
                    {
                        "occurrence_id": 0,
                        "section": "Gallery",
                        "status": "failed",
                        "alt": "Image",
                        "display_url": "https://example.org/a.png",
                    }
                ],
            },
        )
        pages.append({"id": str(i), "revision_id": 1, "title": raw["title"], "path": f"raw/wikigg/{i}.json"})
    report = root / "reports/crawl-fixture.json"
    save(report, {"job_id": "fixture", "target": 200, "pages": pages, "counts": {"successful": 200}})
    return report


def test_pipeline_is_offline_deterministic_and_does_not_attach_gallery_to_lore(tmp_path):
    config = load_settings()
    config["data_dir"] = tmp_path / "data"
    job = make_sample(config["data_dir"])
    with patch("httpx.Client", side_effect=AssertionError("Network forbidden")):
        a = run_clean(config, tmp_path / "a", crawl_report=job, limit=1)
        b = run_clean(config, tmp_path / "b", crawl_report=job, limit=1)
    assert a["csv_validation"] == b["csv_validation"]
    assert a["input_artifacts_unchanged"]
    with (tmp_path / "a/lore_clean.csv").open(encoding="utf-8-sig", newline="") as f:
        assert all(json.loads(r["image_ids"]) == [] for r in csv.DictReader(f))
    with (tmp_path / "a/images.csv").open(encoding="utf-8-sig", newline="") as f:
        assert next(csv.DictReader(f))["scope_status"] == "review"
    with pytest.raises(ValueError, match="new or empty"):
        run_clean(config, tmp_path / "a", crawl_report=job, limit=1)


def test_revision_mismatch_stops_pipeline(tmp_path):
    config = load_settings()
    config["data_dir"] = tmp_path / "data"
    job = make_sample(config["data_dir"])
    path = config["data_dir"] / "raw/wikigg/0.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["revision_id"] = 2
    save(path, raw)
    with pytest.raises(ValueError, match="revision"):
        run_clean(config, tmp_path / "out", crawl_report=job, limit=1)


def test_csv_validator_rejects_cross_page_image_links(tmp_path):
    text = "Lore."
    row = {k: "" for k in LORE}
    row.update(
        record_id="1",
        source_id="A",
        revision_id="1",
        section="Lore",
        text=text,
        content_hash=sha256(text.encode()),
        scope_status="base",
        image_ids='["img"]',
    )
    image = {k: "" for k in IMAGES}
    image.update(
        occurrence_id="1",
        source_id="B",
        revision_id="1",
        section="Lore",
        image_id="img",
        local_path="some.png",
        scope_status="base",
    )
    expected = {"lore_clean.csv": [row], "review.csv": [], "images.csv": [image]}
    for name, headers in [("lore_clean.csv", LORE), ("review.csv", REVIEW), ("images.csv", IMAGES)]:
        csv_write(tmp_path / name, headers, expected[name])
    with pytest.raises(ValueError, match="cross-section"):
        verify_csv(tmp_path, expected)


REAL_EXPECTATIONS = json.loads(
    (Path(__file__).parents[1] / "fixtures/cleaning_s2_expectations.json").read_text(encoding="utf-8")
)["pages"]


@pytest.mark.parametrize("case", REAL_EXPECTATIONS, ids=[p["title"] for p in REAL_EXPECTATIONS])
def test_local_20_page_source_literals_survive_cleaning(case):
    # These local-data regressions skip in CI when ignored crawl artifacts are absent.
    from core.text.normalize import normalized_key
    from ingest.artifacts import read
    from ingest.filter.rules import filter_document

    data = Path(__file__).resolve().parents[2] / "data/raw/wikigg" / (case["source_id"] + ".json")
    if not data.exists():
        pytest.skip("Local raw sample is not committed")
    raw = read(data)
    if raw["revision_id"] != case["revision_id"]:
        pytest.skip("Source revision differs; review expectations first")
    cleaned = filter_document(raw, load_settings()["clean"])
    text = normalized_key(" ".join(s["text"] for s in cleaned["sections"]))
    assert all(phrase in text for phrase in case["source_literals_preserved"])


def test_inline_marker_audited_once_with_its_heading_context():
    r = clean(
        '<div>Opening prose<h2>Background<span class="mw-editsection">[edit]</span></h2>'
        'More prose<p>Text<sup class="reference">[1]</sup></p>Trailing prose</div>'
    )
    markers = [x for x in r["removed"] if x["reason"] == "inline_reference_or_edit_marker"]
    assert len(markers) == 2
    assert all(x["section"] == "Background" for x in markers)
    assert len({x["location"] for x in markers}) == 2
