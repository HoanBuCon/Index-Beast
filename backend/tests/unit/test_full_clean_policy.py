from core.text.html_clean import clean_html
from core.text.lore_policy import block_decision, block_metadata, context_groups


def test_dlc_and_short_description_are_kept():
    block = {"kind": "prose", "text": "A splinter of the Scadutree.", "notes": []}
    assert block_decision("Description", block)[0] == "keep"
    assert block_decision("Acquisition", block)[0] == "excluded"
    assert block_decision("Cut content", block)[0] == "review"


def test_description_tabs_and_version_noise():
    html = """<div class="mw-parser-output" lang="en"><h2 id="Description">Description</h2>
    <div style="font-style:italic"><article class="tabber__panel" id="en" data-title="English">
    <p><span style="float:right">1.07</span><span style="float:right">Source:</span>First lore.</p>
    <p>Second lore.</p></article><article class="tabber__panel" id="jp" data-title="JP">
    <p>影樹の破片</p></article><article class="tabber__panel" id="fr" data-title="🇫🇷"><p>Histoire.</p>
    </article></div></div>"""
    parsed = clean_html(html, title="Fixture", capture_context=True)
    groups = context_groups(parsed["sections"][0], "en")
    assert [len(g) for g in groups] == [2, 1, 1]
    assert [block_metadata(g[0], "en")["lang"] for g in groups] == ["en", "ja", "fr"]
    assert all(block_metadata(g[0], "en")["source_type"] == "in_game_text" for g in groups)
    assert "1.07" not in parsed["sections"][0]["text"]
    assert "Second lore." in parsed["sections"][0]["text"]
    assert len([r for r in parsed["removed"] if r["reason"] == "literal_description_version_label"]) == 2


def test_dialogue_keeps_trigger_and_does_not_infer_speaker():
    html = (
        '<div class="mw-parser-output"><h2>Dialogue</h2><table><tr><th>English Dialogue</th></tr>'
        "<tr><th>After returning</th></tr><tr><td>Welcome back.</td></tr></table></div>"
    )
    s = clean_html(html, title="NPC", capture_context=True)["sections"][0]
    turn = s["blocks"][0]["turns"][0]
    assert turn["speaker"] is None and turn["trigger"] == "After returning"
    assert "Welcome back." in turn["text"]


def test_table_review_and_explicit_language_are_not_guessed():
    b = {"kind": "table", "text": "Field | lore", "notes": []}
    assert block_decision("Notes", b)[0] == "review"
    assert block_metadata(dict(b, variant_context={"label": "🇩🇪"}), "en")["lang"] == "de"


def test_combat_is_reviewed_but_dialogue_is_preserved():
    block = {"kind": "prose", "text": "Attack with the sword.", "notes": []}
    assert block_decision("Boss Fight > Phase 1", block)[0] == "review"
    assert block_decision("Boss Fight > Dialogue", dict(block, kind="dialogue"))[0] == "keep"
    assert block_decision("Cut content > Description", dict(block, literal_description=True))[0] == "review"
