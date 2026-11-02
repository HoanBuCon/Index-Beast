from pathlib import Path

from bs4 import BeautifulSoup
from tokenizers import Tokenizer, models

from ingest.artifacts import save, sha256
from ingest.debug.raw_scope_study import page_probe, study

CONFIG = {"dlc_markers": ["Shadow of the Erdtree", "Scadutree", "Shadow Keep"], "base_places": ["Limgrave"]}


def probe(title, html):
    return page_probe({"title": title}, BeautifulSoup(html, "html.parser"), CONFIG)


def test_generic_2022_label_is_not_base_proof():
    result = probe("Unknown Item", '<div class="mw-parser-output"><p>Item in ELDEN RING (2022).</p></div>')
    assert result["partition"] == "unresolved_review"
    assert result["generic_2022_intro"]


def test_empty_paragraphs_do_not_hide_dlc_definition():
    result = probe(
        "Boss",
        '<div class="mw-parser-output"><p></p><p> </p><p>Boss is a mandatory boss in Shadow of the Erdtree.</p></div>',
    )
    assert result["partition"] == "dlc_candidate"
    assert result["reason"] == "explicit_dlc_definition"


def test_dlc_mention_does_not_exclude_whole_page():
    result = probe(
        "Base Character",
        '<div class="mw-parser-output"><p>Lives in Limgrave.</p>'
        "<h2>Later appearances</h2><p>Also mentioned in Shadow of the Erdtree.</p></div>",
    )
    assert result["partition"] == "mixed_or_dlc_review"


def test_navigation_does_not_supply_scope_evidence():
    result = probe(
        "Unknown", '<div class="mw-parser-output"><div class="navbox">Shadow Keep</div><p>Unclassified lore.</p></div>'
    )
    assert result["partition"] == "unresolved_review"


def test_study_freezes_cohort_and_supports_relative_run_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    run = data / "crawl"
    html = '<div class="mw-parser-output" lang="en"><p>Lives in Limgrave.</p></div>'
    raw = {
        "source_id": "1",
        "source": "wikigg",
        "revision_id": 2,
        "title": "Fixture",
        "content": html,
        "content_hash": sha256(html.encode()),
        "url": "https://example.org/1",
        "categories": [],
    }
    save(data / "raw" / "1.json", raw)
    # An old/unselected snapshot must not enter the study cohort.
    save(data / "raw" / "old.json", dict(raw, source_id="2"))
    entry = {
        "id": "1",
        "title": "Fixture",
        "revision_id": 2,
        "path": "raw/1.json",
        "media_manifest": "crawl/media/1.json",
    }
    save(
        run / "report.json",
        {
            "status": "partial",
            "finished_at": "2026-10-29T00:00:00Z",
            "job_id": "fixture",
            "pages": [entry],
            "counts": {"successful": 1},
            "inventory_pages": 1,
        },
    )
    save(run / "checkpoint.json", {"1": entry})
    save(run / "inventory.json", {"pages": {"1": {}}})
    save(run / "media" / "1.json", {"source_id": "1", "revision_id": 2, "images": []})
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.save(str(tmp_path / "tokenizer.json"))
    original = (data / "raw" / "1.json").read_bytes()
    result = study(data, Path("data/crawl"), tmp_path / "tokenizer.json", tmp_path / "study")
    assert result["cohort_pages"] == result["counts"]["pages_read"] == 1
    assert result["changed_inputs"] == result["failures"] == result["simulation"]["errors"] == []
    assert (data / "raw" / "1.json").read_bytes() == original
