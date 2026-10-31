"""Bảng/lưới chỉ số trong infobox (.pi-smart-group) không được mất mà không để lại dấu vết.

HTML rút gọn theo cấu trúc portable-infobox thật của wiki.gg (Moonveil, Chain Coif, Flame Cleanse Me, Malenia).

Phụ trách: TV1 · [S2] Sửa cleaner giữ bảng chỉ số infobox (đề xuất dữ liệu #1)
"""

from bs4 import BeautifulSoup

from core.text.html_clean import clean_html
from core.text.lore_policy import block_decision

WEAPON = """<div class="mw-parser-output" lang="en"><aside class="portable-infobox">
<h2 class="pi-item pi-title">Moonveil</h2>
<section class="pi-item pi-group"><section class="pi-item pi-smart-group">
<div class="pi-smart-group-body"><div class="pi-smart-data-value pi-data-value">名刀月隠<br>(Meitō Tsukikakure)</div>
</div>
</section></section>
<section class="pi-item pi-group"><h2 class="pi-item pi-header">Basic Information</h2>
<div class="pi-item pi-data" data-source="type"><h3 class="pi-data-label">Type</h3>
<div class="pi-data-value">Katana</div></div>
<div class="pi-item pi-data" data-source="weight"><h3 class="pi-data-label">Weight</h3>
<div class="pi-data-value">6.5</div></div>
</section>
<section class="pi-item pi-group"><h2 class="pi-item pi-header">Stats</h2>
<section class="pi-item pi-smart-group"><div class="pi-smart-group-head">
<h3 class="pi-smart-data-label pi-data-label">Stats</h3></div>
<table class="table center"><tr><th colspan="4">Stats</th></tr>
<tr><th colspan="2">Attack Power</th><th colspan="2">Guarded<br>Damage Negation</th></tr>
<tr><td>Physical:</td><td>73</td><td>Physical:</td><td>31</td></tr>
<tr><td>Magic:</td><td>87</td><td>Magic:</td><td>57</td></tr></table></section>
<section class="pi-item pi-smart-group"><div class="pi-smart-group-head">
<h3 class="pi-smart-data-label pi-data-label">Attributes</h3></div>
<table class="table center"><tr><th colspan="4">Attributes</th></tr>
<tr><th>Attribute</th><th>Required</th><th>Scaling</th></tr>
<tr><td>Strength:</td><td>12 \\1h<br>8 \\2h</td><td>E</td></tr>
<tr><td>Intelligence:</td><td>23</td><td>C</td></tr></table></section>
</section></aside><p>Moonveil is a melee armament.</p></div>"""

SPELL = """<div class="mw-parser-output"><aside class="portable-infobox">
<h2 class="pi-item pi-title">Flame, Cleanse Me</h2>
<section class="pi-item pi-group"><h2 class="pi-item pi-header">Attributes Required</h2>
<section class="pi-item pi-smart-group"><div class="pi-smart-group-head">
<h3 class="pi-smart-data-label pi-data-label">Int</h3><h3 class="pi-smart-data-label pi-data-label">Fth</h3></div>
<div class="pi-smart-group-body"><div class="pi-smart-data-value pi-data-value">0</div>
<div class="pi-smart-data-value pi-data-value">12</div></div></section></section></aside></div>"""

ENEMY_PLACEHOLDER = """<div class="mw-parser-output"><aside class="portable-infobox">
<h2 class="pi-item pi-title">Dominula Dancer</h2><section class="pi-item pi-smart-group">
<table><tr><th colspan="5">Damage Negation:</th></tr><tr><td>Standard:</td><td>%</td><td></td><td>Magic:</td>
<td>%</td></tr>
</table></section></aside></div>"""

BOSS_TWO_PHASES = """<div class="mw-parser-output"><aside class="portable-infobox">
<h2 class="pi-item pi-title">Malenia, Blade of Miquella</h2>
<section class="pi-item pi-smart-group"><div class="pi-smart-group-head"><h3 class="pi-smart-data-label">Defense</h3>
</div>
<div class="pi-smart-group-body"><div class="pi-smart-data-value">125</div></div></section></aside>
<aside class="portable-infobox"><h2 class="pi-item pi-title">Malenia, Goddess of Rot</h2>
<section class="pi-item pi-smart-group"><div class="pi-smart-group-head"><h3 class="pi-smart-data-label">Defense</h3>
</div>
<div class="pi-smart-group-body"><div class="pi-smart-data-value">125</div></div></section></aside></div>"""


def stats_blocks(parsed):
    return [b for s in parsed["sections"] for b in s["blocks"] if b["kind"] == "infobox_stats"]


def test_weapon_attack_power_and_attributes_are_rendered_with_group_names():
    parsed = clean_html(WEAPON, title="Moonveil", capture_context=True)
    stats, attributes = (b["text"].split("\n") for b in stats_blocks(parsed))

    assert stats == [
        "Stats",
        "Attack Power / Physical: 73",
        "Guarded Damage Negation / Physical: 31",
        "Attack Power / Magic: 87",
        "Guarded Damage Negation / Magic: 57",
    ]
    assert attributes[:3] == ["Stats", "Attributes", "Attribute | Required | Scaling"]
    assert "Strength: | 12 \\1h 8 \\2h | E" in attributes
    assert "Intelligence: | 23 | C" in attributes


def test_stats_stay_excluded_until_gameplay_scope_is_approved():
    parsed = clean_html(WEAPON, title="Moonveil", capture_context=True)

    decisions = {block_decision("Infobox", b) for b in stats_blocks(parsed)}

    assert decisions == {("excluded", "infobox_stats_group")}  # vào review.csv, chưa vào chunk


def test_label_value_grid_and_unlabeled_value():
    spell = stats_blocks(clean_html(SPELL, title="Flame, Cleanse Me"))
    weapon = clean_html(WEAPON, title="Moonveil")

    assert [b["text"] for b in spell] == ["Attributes Required\nInt: 0, Fth: 12"]
    assert [r["reason"] for r in weapon["removed"] if "Meitō" in r["text"]] == ["infobox_unlabeled_value"]


def test_placeholder_table_without_numbers_is_audited_not_kept():
    parsed = clean_html(ENEMY_PLACEHOLDER, title="Dominula Dancer")

    assert stats_blocks(parsed) == []
    assert [r["reason"] for r in parsed["removed"]] == ["infobox_placeholder_stats"]


def test_second_infobox_is_labelled_with_its_own_title():
    texts = [b["text"] for b in stats_blocks(clean_html(BOSS_TWO_PHASES, title="Malenia, Blade of Miquella"))]

    assert texts == ["Defense: 125", "Malenia, Goddess of Rot\nDefense: 125"]


def test_no_smart_group_text_is_silently_dropped():
    """Mọi chữ trong .pi-smart-group phải nằm trong block giữ/loại theo policy hoặc trong ledger `removed`."""
    for html, title in ((WEAPON, "Moonveil"), (SPELL, "Flame, Cleanse Me"), (ENEMY_PLACEHOLDER, "Dominula Dancer")):
        parsed = clean_html(html, title=title)
        captured = " ".join(
            [b["text"] for s in parsed["sections"] for b in s["blocks"]] + [r["text"] for r in parsed["removed"]]
        )
        captured = " ".join(captured.split())
        for group in BeautifulSoup(html, "html.parser").select(".pi-smart-group"):
            for cell in group.select("td, .pi-smart-data-value"):
                value = " ".join(cell.get_text(" ", strip=True).split())
                if value and value != "%":
                    assert value.replace(" ", "") in captured.replace(" ", ""), (title, value)
