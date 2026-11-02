"""Pure S2 base+SotE content policy; release uncertainty does not block lore."""

import re
from itertools import groupby

GAMEPLAY = re.compile(
    r"(?:^| > )(?:Patch Notes|Strategies|Moveset|Frame data|Shop inventory|Effects?|Boosting|Crafting(?: Materials)?|"
    r"Acquisition|Drops|Notable Loot|Stats|Attributes|Attack Power|Damage Negation|Resistances)(?:$| > )",
    re.I,
)
FIELDS = re.compile(
    r"^(?:type|category|max[ .]*(?:held|stored)|item effect|obtained|online trade|attack type|"
    r"skill|fp cost|stamina cost|buy price|sell price|scaling|requirements?)\s*:",
    re.I,
)


def block_decision(section, block):
    if re.search(r"Nightreign|Tarnished Edition", section + " " + block["text"], re.I):
        return "review", "outside_base_sote_or_cross_game_context"
    if re.search(r"(?:^| > )(?:Unused|Cut content|Cut dialogue)(?:$| > )", section, re.I):
        return "review", "cut_or_unused_not_confirmed_canon"
    if block["kind"] == "dialogue" or block.get("literal_description"):
        return "keep", "literal_game_text"
    if re.search(r"(?:^| > )Boss Fight(?:$| > )", section, re.I):
        return "review", "combat_section_may_contain_lore"
    if block["kind"] == "infobox_stats":
        # Chỉ số trong infobox: giữ trong review.csv, chưa vào corpus cho tới khi chốt phạm vi gameplay
        return "excluded", "infobox_stats_group"
    if GAMEPLAY.search(section):
        return "excluded", "gameplay_section"
    if block["kind"] == "table" or block.get("notes"):
        return "review", "unclassified_structure"
    if block["kind"] == "infobox" and FIELDS.search(block["text"]):
        return "excluded", "gameplay_infobox_field"
    if "\ufffd" in block["text"]:
        return "review", "encoding_replacement_character"
    return "keep", "lore_structure_with_source_context"


def block_metadata(block, html_lang):
    variant = block.get("variant_context") or {}
    label = variant.get("label") or ""
    labelled = {
        "JP": "ja",
        "JA": "ja",
        "EN": "en",
        "VI": "vi",
        "DE": "de",
        "FR": "fr",
        "ES": "es",
        "🇨🇳": "zh",
        "🇩🇪": "de",
        "🇫🇷": "fr",
        "🇪🇸": "es",
        "🇮🇹": "it",
        "🇰🇷": "ko",
        "🇷🇺": "ru",
        "🇵🇱": "pl",
        "🇵🇹": "pt",
        "🇹🇭": "th",
    }
    if label in labelled:
        lang = labelled[label]
    elif "🇯🇵" in label or re.search(r"Japanese|日本語", label, re.I):
        lang = "ja"
    elif re.search(r"English", label, re.I) or "🏴" in label:
        lang = "en"
    elif re.search(r"[\u3040-\u30ff\u3400-\u9fff]", block["text"]):
        lang = "unknown"
    else:
        lang = html_lang if html_lang in {"en", "ja", "vi"} else "unknown"
    literal = block.get("literal_description") or block["kind"] == "dialogue"
    source_type = "in_game_text" if literal else "wiki_prose"
    if not literal and re.search(
        r"\bspeculat\w*|\btheori[sz]\w*|\bmost likely\b|\blikely inspired\b|\bmay be a nod\b", block["text"], re.I
    ):
        source_type = "speculation"
    return {
        "lang": lang,
        "source_type": source_type,
        "source_type_evidence": "literal_item_description_or_dialogue" if literal else "wiki_article_structure",
    }


def context_groups(section, html_lang):
    def key(block):
        decision, reason = block_decision(section["section"], block)
        meta = block_metadata(block, html_lang)
        variant = block.get("variant_context") or {}
        return (
            decision,
            reason,
            meta["lang"],
            meta["source_type"],
            variant.get("anchor"),
            variant.get("label"),
            block["kind"],
        )

    return [list(group) for _, group in groupby(section["blocks"], key=key)]
