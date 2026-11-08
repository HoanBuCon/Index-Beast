from bs4 import BeautifulSoup

from core.text.chunking import chunk_section
from core.text.html_clean import clean_html
from core.text.structured_tables import extract, grid
from tests.unit.test_full_chunk import fixture


def parse(table, title="Item"):
    soup = BeautifulSoup('<div class="mw-parser-output" lang="en">' + table + "</div>", "html.parser")
    return list(extract(soup, title, {}).values())[0]


def test_crystal_rowspans_do_not_shift_second_attack_to_guard():
    t = parse("""<table><tr><th>Level</th><th>Atk</th><th>STR Scaling</th><th>Grd Boost</th></tr>
    <tr><td rowspan="2">+0</td><td>106</td><td rowspan="2">D<p>0.45</p></td><td rowspan="2">33</td></tr>
    <tr><td><span style="color:cyan">68</span></td></tr></table>""")
    facts = t["facts"]
    attack = [f for f in facts if f["stat_name"] == "Atk"]
    assert {f["value"] for f in attack} == {"106", "68"}
    assert all(f["decision"] == "review" and f["damage_type"] is None for f in attack)
    guard = [f for f in facts if f["stat_name"] == "Grd Boost"]
    assert len(guard) == 1 and guard[0]["value"] == "33" and guard[0]["decision"] == "keep"
    grade = next(f for f in facts if f["stat_name"] == "STR Scaling")
    assert grade["scaling_grade"] == "D" and grade["coefficient"] == "0.45"


def test_multilevel_header_and_attribute_column_roles():
    t = parse("""<table><tr><th rowspan="2">Attribute</th><th colspan="2">Attributes</th></tr>
    <tr><th>Required</th><th>Scaling</th></tr><tr><td>Strength:</td><td>12</td><td>E</td></tr></table>""")
    assert any(f["stat_name"] == "Attributes / Required" and f["value"] == "12" for f in t["facts"])
    assert any(f["stat_name"] == "Attributes / Scaling" and f["value"] == "E" for f in t["facts"])


def test_grid_zero_rowspan_and_conflict_are_not_silently_fixed():
    soup = BeautifulSoup(
        '<table><tbody><tr><td rowspan="0">A</td><td>B</td></tr><tr><td>C</td></tr></tbody></table>', "html.parser"
    )
    rows, _, errors = grid(soup.table)
    assert not errors and rows[1][0]["text"] == "A" and rows[1][1]["text"] == "C"
    t = parse('<table><tr><td>X</td><td rowspan="2">Y</td></tr><tr><td colspan="2">Z</td></tr></table>')
    assert t["grid_issues"] and t["decision"] == "review" and not t["facts"]


def test_inventory_placeholder_partial_keep_and_no_header_review():
    t = parse(
        "<table>"
        "<tr>"
        "<th>Icon</th>"
        "<th>Name</th>"
        "<th>Effect</th>"
        "</tr>"
        "<tr>"
        "<td>"
        "</td>"
        "<td>Item +1</td>"
        "<td>Boost 0%</td>"
        "</tr>"
        "<tr>"
        "<td>"
        "</td>"
        "<td>Item +2</td>"
        "<td>?</td>"
        "</tr>"
        "</table>"
    )
    assert any(f["value"] == "Boost 0%" and f["decision"] == "keep" for f in t["facts"])
    assert next(f for f in t["facts"] if f["value"] == "?")["decision"] == "review"
    assert parse("<table><tr><td>unlabelled</td><td>14</td></tr></table>")["decision"] == "review"


def test_quote_and_cross_game_do_not_become_unsupported_facts():
    t = parse("<table><tr><td>“</td><td>A literal source quotation.</td><td>”</td></tr></table>")
    assert t["decision"] == "keep" and t["blocks"][0]["text"] == "A literal source quotation."
    t = parse(
        "<table><tr><th>Name</th><th>Effect</th></tr><tr><td>X</td><td>Effect</td></tr></table>", title="Nightreign"
    )
    assert t["decision"] == "review" and not t["blocks"]


def test_dialogue_columns_and_growth_keep_source_roles():
    t = parse(
        "<h2>Dialogue</h2>"
        "<table>"
        "<tr>"
        "<th>Condition</th>"
        "<th>Speaker</th>"
        "<th>Dialogue</th>"
        "</tr>"
        "<tr>"
        "<td>When attacked</td>"
        "<td>NPC</td>"
        "<td>Help!</td>"
        "</tr>"
        "</table>"
    )
    assert "Condition: When attacked" in t["blocks"][0]["text"] and "Speaker: NPC" in t["blocks"][0]["text"]
    t = parse("<table><tr><th>Level</th><th>Atk</th></tr><tr><td>↑/Lv</td><td>+14.4%</td></tr></table>")
    assert next(f for f in t["facts"] if f["stat_name"] == "Atk")["value"] == "+14.4%"


def test_nested_inventory_and_oversized_rows_are_reviewed_not_cut():
    soup = BeautifulSoup(
        '<div class="mw-parser-output">'
        "<table>"
        "<tr>"
        "<td>"
        "<table>"
        "<tr>"
        "<th>Name</th>"
        "<th>Effect</th>"
        "</tr>"
        "<tr>"
        "<td>X</td>"
        "<td>Y</td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"
        "</table>"
        "</div>",
        "html.parser",
    )
    tables = list(extract(soup, "Item", {}).values())
    assert len(tables) == 2 and tables[0]["reason"] == "nested_table_container" and tables[1]["blocks"]
    text = "Effect: " + "A long value. " * 300
    s = {
        "section": "Items",
        "lang": "en",
        "text": text,
        "blocks": [{"kind": "table_fact", "text": text, "location": "table:1"}],
    }
    result = chunk_section({"title": "Item"}, s, fixture()[1], 100, 15)
    assert not result["chunks"] and result["reviews"][0]["reason"] == "structured_row_over_budget"


def test_opt_in_renders_catalog_with_labels_and_legacy_stays_review():
    raw = (
        '<div class="mw-parser-output">'
        "<h2>Overview</h2>"
        "<table>"
        "<tr>"
        "<th>Icon</th>"
        "<th>Name</th>"
        "<th>Effect</th>"
        "</tr>"
        "<tr>"
        "<td>"
        "</td>"
        "<td>Spelldrake +1</td>"
        "<td>Magic negation 17%</td>"
        "</tr>"
        "</table>"
        "</div>"
    )
    parsed = clean_html(raw, title="Spelldrake", capture_context=True, preserve_gameplay=True, structured_tables=True)
    block = next(b for s in parsed["sections"] for b in s["blocks"] if b["kind"] == "table_fact")
    assert (
        "Name: Spelldrake +1" in block["text"] and "Effect: Magic negation 17%" in block["text"] and block["fact_ids"]
    )
    old = clean_html(raw, title="Spelldrake", preserve_gameplay=True)
    assert any(b["kind"] == "table" for s in old["sections"] for b in s["blocks"])


def test_dialogue_languages_split_and_source_variant_retained():
    raw = """<div class="mw-parser-output" lang="en"><h2>Dialogue</h2>
    <div class="tabber__panel" id="Original-0"><table>
    <tr><th>Location</th><th>Dialogue</th><th>Dialogue (Japanese)</th></tr>
    <tr><td>Church</td><td>Hello.</td><td>こんにちは。</td></tr></table></div></div>"""
    parsed = clean_html(raw, title="NPC", capture_context=True, preserve_gameplay=True, structured_tables=True)
    from core.text.lore_policy import block_metadata

    blocks = [b for s in parsed["sections"] for b in s["blocks"] if b["kind"] == "table_fact"]
    assert len(blocks) == 2
    en = next(b for b in blocks if block_metadata(b, "en")["lang"] == "en")
    assert "こんにちは" not in en["text"] and "Location: Church" in en["text"]
    assert en["variant_context"]["label"] == "Original-0"


def test_attribute_identity_and_crafting_quantities_remain_distinct():
    t = parse("""<table><tr><th colspan="3">Stats</th></tr>
    <tr><th>Attribute</th><th>Required</th><th>Scaling</th></tr>
    <tr><td>Strength:</td><td>8</td><td>D</td></tr></table>""")
    f = next(f for f in t["facts"] if f["value"] == "8")
    assert f["decision"] == "keep" and f["row_key"] == "Attribute: Strength"
    t = parse("""<table><tr><th>Item name</th><th>#</th><th>Material name</th><th>#</th></tr>
    <tr><td rowspan="2">Pot</td><td rowspan="2">x1</td><td>Resin</td><td>2</td></tr>
    <tr><td>Flower</td><td>3</td></tr></table>""")
    assert any(f["stat_name"] == "Item name / #" and f["value"] == "x1" and f["decision"] == "keep" for f in t["facts"])
    assert any(
        f["stat_name"] == "Material name / #" and f["value"] == "3" and "Flower" in f["row_key"] for f in t["facts"]
    )


def test_duplicated_move_headers_are_not_facts_and_icon_alt_is_source_label():
    t = parse("""<table><tr><th>Move Name</th><th>Move Name</th><th>Move Name</th></tr>
    <tr><td>Phase</td><td>Damage Type</td><td>Can Be Parried</td></tr></table>""")
    assert all(f["decision"] == "review" for f in t["facts"])
    t = parse("""<table><tr><th>Name</th><th><img alt="ER Custom Stat Icon Attack Power Lightning.png"></th></tr>
    <tr><td>Weapon</td><td>0</td></tr></table>""")
    assert any(
        f["stat_name"] == "Attack Power Lightning" and f["value"] == "0" and f["decision"] == "keep" for f in t["facts"]
    )


def test_fact_exports_separate_review_and_keep_nullable_values(tmp_path):
    import csv
    import json

    from ingest.transform.table_artifacts import attach, export

    raw_html = """<div class="mw-parser-output" lang="en"><table>
    <tr><th>Name</th><th>Effect</th></tr><tr><td>A</td><td>0</td></tr>
    <tr><td>B</td><td>?</td></tr></table></div>"""
    raw = {
        "source_id": "1",
        "source": "wikigg",
        "title": "Item",
        "revision_id": 1,
        "fetched_at": "2026-11-09T00:00:00Z",
        "url": "https://example.test/Item",
        "content_hash": "a" * 64,
    }

    def build():
        parsed = clean_html(
            raw_html, title="Item", capture_context=True, preserve_gameplay=True, structured_tables=True
        )
        return attach(parsed, raw, tmp_path / "raw.json", "s3-full-clean-2.0")

    tables, facts = build()
    assert [f["fact_id"] for f in facts] == [f["fact_id"] for f in build()[1]]
    export(tmp_path / "tables", tables, facts)
    clean = [json.loads(x) for x in (tmp_path / "tables/facts_clean.jsonl").read_text().splitlines()]
    assert all(f["decision"] == "keep" for f in clean) and any(f["value"] == "0" for f in clean)
    with (tmp_path / "tables/facts_clean.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert all(r["decision"] == "keep" and r["coefficient"] == "" for r in rows)
    assert any(f["value"] == "?" and f["decision"] == "review" for f in facts)


def test_decorative_separators_and_unresolved_note_qualifiers_are_not_clean():
    from core.text.table_quality import review_reason

    assert review_reason("-----") == "decorative_source_separator"
    assert review_reason("Sword [ note 1 ]") == "unresolved_source_note"
    assert review_reason("30", "Name: Sword [ note 1 ]") == "unresolved_source_note"
    assert review_reason("Smithing Stone [1]") is None
    assert review_reason("-") is None and review_reason("0") is None
    t = parse("""<table><tr><th>Name</th><th>Effect</th></tr>
    <tr><td>A</td><td>-----</td></tr><tr><td>B</td><td>Drop [ note 1 ]</td></tr></table>""")
    assert all(f["decision"] == "review" for f in t["facts"] if f["stat_name"] == "Effect")
