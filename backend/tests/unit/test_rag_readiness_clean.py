from core.text.chunking import chunk_section, split_unit
from core.text.html_clean import clean_html
from core.text.lore_policy import block_decision, block_metadata, context_groups, editorial_template
from tests.unit.test_full_chunk import fixture
from tests.unit.test_infobox_stats import WEAPON


def test_full_mode_preserves_source_stats_but_legacy_stays_unchanged():
    parsed = clean_html(WEAPON, title="Moonveil", capture_context=True, preserve_gameplay=True)
    blocks = [b for s in parsed["sections"] for b in s["blocks"]]
    stats = [b for b in blocks if b["kind"] == "infobox_stats"]
    assert "Attack Power / Physical: 73" in stats[0]["text"]
    assert "Guarded Damage Negation / Physical: 31" in stats[0]["text"]
    assert "Attributes" in stats[1]["table_header"]
    assert all(block_decision("Infobox", b, gameplay=True)[0] == "keep" for b in stats)
    assert all(block_decision("Infobox", b)[0] == "excluded" for b in stats)


def test_fields_group_together_and_costs_are_not_production_metadata():
    html = """<div class="mw-parser-output"><aside class="portable-infobox">
    <div class="pi-data" data-source="weight"><h3 class="pi-data-label">Weight</h3>
    <div class="pi-data-value">0</div></div><div class="pi-data" data-source="fp_cost">
    <h3 class="pi-data-label">FP Cost</h3><div class="pi-data-value">- (15 20)</div></div>
    <div class="pi-data" data-source="voice"><div class="pi-data-value">Actor</div></div>
    </aside></div>"""
    parsed = clean_html(html, title="Item", capture_context=True, preserve_gameplay=True)
    section = next(s for s in parsed["sections"] if s["kind"] == "infobox")
    groups = context_groups(section, "en", gameplay=True)
    assert len(groups) == 1 and len(groups[0]) == 2
    assert [b["text"] for b in groups[0]] == ["Weight: 0", "FP Cost: - (15 20)"]
    assert any(r["text"] == "Actor" for r in parsed["removed"])


def test_flags_and_editorial_content_are_not_mislabelled_as_english_or_canon():
    for flag, language in [("🇧🇷", "pt"), ("🇹🇼", "zh"), ("🇿🇿", "unknown")]:
        b = {"kind": "prose", "text": "Example", "variant_context": {"label": flag}}
        assert block_metadata(b, "en")["lang"] == language
    b = {"kind": "prose", "text": "A cut quest.", "notes": []}
    assert block_decision("Behind the scenes", b, gameplay=True)[0] == "review"
    assert editorial_template("Elden Ring Talisman Template", "English line 1")
    assert not editorial_template("Moonveil", "English line 1")


def test_oversized_stats_repeat_table_context_with_exact_source_slices():
    text = "Attributes\nAttribute | Required | Scaling\n" + "Strength: | 12 | E\n" * 100
    block = {
        "text": text,
        "kind": "infobox_stats",
        "location": "dom:1:table",
        "table_header": "Attributes / Required / Scaling",
    }
    section = {"section": "Infobox", "blocks": [block], "text": text, "lang": "en"}
    result = chunk_section({"title": "Moonveil"}, section, fixture()[1], 100, 15)
    assert len(result["chunks"]) > 1
    assert all("Table header: Attributes / Required / Scaling" in c["embedding_text"] for c in result["chunks"])
    assert all(c["text"] == text[c["start_char"] : c["end_char"]] and c["token_count"] <= 100 for c in result["chunks"])


def test_gameplay_prose_restored_but_unclassified_tables_and_cut_content_reviewed():
    b = {"kind": "prose", "text": "Dropped by a knight.", "notes": []}
    assert block_decision("Acquisition", b, gameplay=True)[0] == "keep"
    assert block_decision("Acquisition", dict(b, kind="table"), gameplay=True)[0] == "excluded"
    assert block_decision("Cut content > Description", dict(b, literal_description=True), gameplay=True)[0] == "review"
    assert block_decision("Infobox", {"kind": "infobox", "text": "Sell Price: ?"}, gameplay=True)[0] == "review"
    assert block_decision("Infobox", {"kind": "infobox", "text": "Weight: 0"}, gameplay=True)[0] == "keep"


def test_fitting_infobox_keeps_passive_with_its_source_stats():
    blocks = [
        {"kind": "infobox", "text": "Weight: 5.5", "location": "dom:1"},
        {"kind": "infobox_stats", "text": "Attack Power / Physical: 115", "location": "dom:2"},
        {"kind": "infobox", "text": "effects: Causes blood loss buildup (45)", "location": "dom:3"},
    ]
    text = "\n".join(b["text"] for b in blocks)
    section = {"kind": "infobox", "section": "Infobox", "lang": "en", "blocks": blocks, "text": text}
    result = chunk_section({"title": "Uchigatana"}, section, fixture()[1], 100, 15)
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["text"] == text
    assert result["chunks"][0]["source_locations"] == ["dom:1", "dom:2", "dom:3"]


def test_japanese_source_tab_overrides_copied_english_table_header():
    html = """<div class="mw-parser-output"><h2>Dialogue</h2><div class="tabber__panel" data-title="JP">
    <table><tr><td>English Dialogue</td></tr><tr><th>Generic greeting</th></tr>
    <tr><td>ああ、よく来てくれたな。我が弟子よ</td></tr></table></div></div>"""
    parsed = clean_html(html, title="Sellen", capture_context=True, preserve_gameplay=True)
    turn = next(b for s in parsed["sections"] for b in s["blocks"] if b["kind"] == "dialogue")["turns"][-1]
    assert turn["lang"] == "ja" and turn["language_evidence"] == "source_tab_label"
    assert turn["trigger"] == "Generic greeting" and "我が弟子よ" in turn["text"]
    unlabelled = html.replace('class="tabber__panel" data-title="JP"', 'class="panel"')
    parsed = clean_html(unlabelled, title="Sellen", preserve_gameplay=True)
    turn = next(b for s in parsed["sections"] for b in s["blocks"] if b["kind"] == "dialogue")["turns"][-1]
    assert turn["lang"] == "unknown"


def test_explicit_speculation_is_not_promoted_to_game_text():
    assert (
        block_metadata({"kind": "prose", "text": "It's possible that this may imply a connection."}, "en")[
            "source_type"
        ]
        == "speculation"
    )


def test_overlap_does_not_begin_inside_an_english_word():
    text = " ".join("weapon's base damage" for _ in range(150))
    tok = fixture()[1]
    spans = split_unit(text, "passage: Item\n", tok, 100, 15)
    assert len(spans) > 1
    for span in spans:
        assert span["text"] == text[span["start_char"] : span["end_char"]]
        assert span["token_count"] <= 100
        start = span["start_char"]
        assert not (start and text[start].isalnum() and (text[start - 1].isalnum() or text[start - 1] == "'"))


def test_inventory_mentioning_dialogue_is_not_a_dialogue_table():
    html = """<div class="mw-parser-output"><h2>Quest Items</h2><table>
    <tr><th>Image</th><th>Item Name</th><th>Requirements</th></tr>
    <tr><td></td><td>Golden Seed</td><td>Given after exhausting her dialogue.</td></tr>
    </table></div>"""
    parsed = clean_html(html, title="Roderika", capture_context=True, preserve_gameplay=True)
    block = next(b for s in parsed["sections"] for b in s["blocks"] if b["kind"] == "table")
    assert block_decision("Quest Items", block, gameplay=True)[0] == "review"
    assert "Golden Seed" in block["text"]


def test_multicolumn_dialogue_is_reviewed_until_columns_are_resolved():
    html = """<div class="mw-parser-output"><h2>Dialogue</h2><table>
    <tr><th>Condition</th><th>Dialogue</th></tr>
    <tr><td>When attacked</td><td>Help me!</td></tr></table></div>"""
    parsed = clean_html(html, title="NPC", capture_context=True, preserve_gameplay=True)
    block = next(b for s in parsed["sections"] for b in s["blocks"] if b["kind"] == "dialogue")
    assert block_decision("Dialogue", block, gameplay=True) == ("review", "unresolved_multicolumn_dialogue")
    assert "When attacked" in block["text"] and "Help me!" in block["text"]
    # A literal pipe in prose or a labelled stat is not sufficient evidence of a broken table.
    assert block_decision("Notes", {"kind": "prose", "text": "Choose A | B."}, gameplay=True)[0] == "keep"
