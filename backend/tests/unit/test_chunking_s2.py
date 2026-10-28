"""Chunk boundaries preserve exact source text and semantic context under a hard token cap."""

from types import SimpleNamespace

from core.text.chunking import chunk_section, prepare_units, split_unit, token_count
from core.text.html_clean import clean_html


class CharacterTokenizer:
    def encode(self, text, add_special_tokens=True):
        return SimpleNamespace(ids=list(range(len(text) + (2 if add_special_tokens else 0))))


TOK = CharacterTokenizer()
DOC = {"title": "NPC"}


def section(text, blocks=None):
    return {
        "section": "Lore",
        "lang": "en",
        "text": text,
        "blocks": blocks or [{"kind": "prose", "text": text, "location": "dom:1"}],
    }


def test_short_source_remains_one_chunk_without_padding():
    r = chunk_section(DOC, section("Short lore."), TOK, cap=100, overlap=10)
    assert len(r["chunks"]) == 1 and r["chunks"][0]["text"] == "Short lore."
    assert r["chunks"][0]["token_count"] == token_count(TOK, r["chunks"][0]["embedding_text"])


def test_unicode_long_source_exact_coverage_and_cap():
    text = ("Tiếng Việt 日本語.\n" * 45).strip()
    spans = split_unit(text, "passage: NPC\nLore\n", TOK, cap=100, overlap=15)
    end = 0
    for span in spans:
        assert span["start_char"] <= end
        assert span["text"] == text[span["start_char"] : span["end_char"]]
        assert span["token_count"] <= 100
        assert "\ufffd" not in span["text"]
        end = span["end_char"]
    assert end == len(text)


def test_final_context_is_included_in_budget():
    r = split_unit("Some long text. " * 25, "passage: NPC\nTrigger: conditional dialogue\n", TOK, cap=100, overlap=20)
    assert all(x["token_count"] <= 100 for x in r)


def test_paragraphs_pack_inside_one_section_and_keep_newlines():
    blocks = [
        {"kind": "prose", "text": "First paragraph.", "location": "a"},
        {"kind": "prose", "text": "Second paragraph.", "location": "b"},
    ]
    s = section("First paragraph.\nSecond paragraph.", blocks)
    units = prepare_units(DOC, s, TOK, cap=200)
    assert len(units) == 1 and units[0]["text"] == s["text"]


def test_typed_dialogue_preserves_every_row_and_language():
    html = """<div class="mw-parser-output"><h2>Dialogue</h2><table>
    <tr><td>English Dialogue</td></tr><tr><th>Before quest</th></tr><tr><td>Hello.</td></tr>
    <tr><th>After quest</th></tr><tr><td>Farewell.</td></tr></table>
    <table><tr><td>Japanese Dialogue</td></tr><tr><th>Before quest</th></tr>
    <tr><td>こんにちは。</td></tr></table></div>"""
    s = clean_html(html, title="NPC")["sections"][0]
    assert len(s["blocks"][0]["turns"]) == 2
    assert s["blocks"][0]["turns"][0]["lang"] == "en"
    assert s["blocks"][1]["turns"][0]["lang"] == "ja"
    assert all(t["speaker"] is None for b in s["blocks"] for t in b["turns"])
    assert "\n".join(t["text"] for b in s["blocks"] for t in b["turns"]) == s["text"]


def test_long_turn_repeats_trigger_without_mixing_other_conditions():
    text = "A long utterance. " * 20
    block = {
        "kind": "dialogue",
        "text": text,
        "location": "table:1",
        "turns": [{"text": text, "trigger": "Before quest", "speaker": None, "lang": "en", "unit_ordinal": 0}],
    }
    s = section(text, [block])
    r = chunk_section(DOC, s, TOK, cap=120, overlap=15)
    assert len(r["chunks"]) > 1
    assert all("Trigger: Before quest" in c["embedding_text"] and c["speaker"] is None for c in r["chunks"])


def test_unfit_context_goes_to_review_without_silent_truncation():
    text = "Hello"
    b = {
        "kind": "dialogue",
        "text": text,
        "location": "table",
        "turns": [{"text": text, "trigger": "x" * 300, "lang": "en", "unit_ordinal": 0}],
    }
    r = chunk_section(DOC, section(text, [b]), TOK, cap=100, overlap=10)
    assert not r["chunks"] and r["reviews"][0]["text"] == text
    assert r["coverage"][0]["status"] == "review"


def test_span_anchor_and_duplicate_variant_context_are_recovered():
    html = """<div class="mw-parser-output"><h2><span class="mw-headline" id="Bosses">Bosses</span></h2>
    <a id="north-label">North</a><article class="tabber__panel" id="north" aria-labelledby="north-label">
    <h3><span class="mw-headline" id="Background">Background</span></h3><p>North story.</p></article>
    <a id="south-label">South</a><article class="tabber__panel" id="south" aria-labelledby="south-label">
    <h3><span class="mw-headline" id="Background">Background</span></h3><p>South story.</p></article></div>"""
    sections = clean_html(html, title="NPC")["sections"]
    sections = [s for s in sections if s["section"] == "Bosses > Background"]
    assert [s["anchor"] for s in sections] == ["north", "south"]
    assert [s["variant_context"]["label"] for s in sections] == ["North", "South"]
    assert all(s["heading_anchor"] == "Background" for s in sections)


def test_single_headline_anchor():
    html = '<main><h2><span class="mw-headline" id="Lore">Lore</span></h2><p>Story.</p></main>'
    assert clean_html(html, title="NPC")["sections"][0]["anchor"] == "Lore"


def test_chunk_cli_uses_config_and_stays_offline(tmp_path):
    from unittest.mock import patch

    from ingest.__main__ import main

    config = {"chunk": {"max_tokens": 400, "overlap_tokens": 25}, "data_dir": tmp_path}
    with (
        patch("ingest.__main__.load_settings", return_value=config),
        patch("ingest.__main__.HttpClient", side_effect=AssertionError("Network forbidden")),
        patch("ingest.chunk.runner.run_chunk", return_value={"status": "completed"}) as run,
    ):
        assert main(["chunk", "--input-dir", "input", "--tokenizer", "local.json", "--output-dir", "output"]) == 0
    assert run.call_args.kwargs == {"cap": 400, "overlap": 25}
