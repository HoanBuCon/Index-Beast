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


def editorial_template(title, html):
    return "template" in title.lower() and bool(re.search(r"English line [123]", html))


def block_decision(section, block, *, gameplay=False):
    if re.search(r"Nightreign|Tarnished Edition", section + " " + block["text"], re.I):
        return "review", "outside_base_sote_or_cross_game_context"
    if re.search(r"(?:^| > )(?:Unused|Cut content|Cut dialogue)(?:$| > )", section, re.I):
        return "review", "cut_or_unused_not_confirmed_canon"
    if gameplay and re.search(r"(?:^| > )Behind the scenes(?:$| > )", section, re.I):
        return "review", "editorial_or_cut_context"
    variant_label = (block.get("variant_context") or {}).get("label")
    if gameplay and variant_label == block["text"].strip() and not block.get("literal_description"):
        return "excluded", "display_variant_label"
    if (
        gameplay
        and block["kind"] == "infobox"
        and re.fullmatch(r"[^:\n]+:\s*(?:\?+|TBA|TBD|Unknown)", block["text"].strip(), re.I)
    ):
        return "review", "unknown_item_field_value"
    if block["kind"] == "dialogue" or block.get("literal_description"):
        if gameplay and "unresolved_multicolumn_dialogue" in block.get("notes", []):
            return "review", "unresolved_multicolumn_dialogue"
        return "keep", "literal_game_text"
    if gameplay and block["kind"] == "table_fact":
        return "keep", "source_structured_table_row"
    if re.search(r"(?:^| > )Boss Fight(?:$| > )", section, re.I):
        return "review", "combat_section_may_contain_lore"
    if block["kind"] == "infobox_stats":
        if gameplay:
            return "keep", "source_labelled_infobox_stats"
        # Chỉ số trong infobox: giữ trong review.csv, chưa vào corpus cho tới khi chốt phạm vi gameplay
        return "excluded", "infobox_stats_group"
    if GAMEPLAY.search(section):
        if gameplay and block["kind"] != "table" and not re.search(r"Patch Notes", section, re.I):
            return "keep", "source_gameplay_prose"
        return "excluded", "gameplay_section"
    if block["kind"] == "table" or block.get("notes"):
        return "review", "unclassified_structure"
    if block["kind"] == "infobox" and FIELDS.search(block["text"]):
        if gameplay:
            return "keep", "source_item_field"
        return "excluded", "gameplay_infobox_field"
    if "\ufffd" in block["text"]:
        return "review", "encoding_replacement_character"
    return "keep", "lore_structure_with_source_context"


def tab_language(label):
    label = label or ""
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
        "🇧🇷": "pt",
        "🇹🇼": "zh",
        "🇹🇭": "th",
    }
    if label in labelled:
        return labelled[label]
    elif "🇯🇵" in label or re.search(r"Japanese|日本語", label, re.I):
        return "ja"
    elif re.search(r"English", label, re.I) or "🏴" in label:
        return "en"
    elif re.search(r"[\U0001f1e6-\U0001f1ff]", label):
        return "unknown"
    return None


def block_metadata(block, html_lang):
    variant = block.get("variant_context") or {}
    lang = block.get("lang_override") or tab_language(variant.get("label"))
    if block.get("lang_override") == "unknown" and block.get("table_type") != "dialogue_table":
        lang = None
    if lang is None:
        lang = (
            "unknown"
            if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", block["text"])
            else (html_lang if html_lang in {"en", "ja", "vi"} else "unknown")
        )
    literal = (
        block.get("literal_description") or block["kind"] == "dialogue" or block.get("table_type") == "dialogue_table"
    )
    source_type = "in_game_text" if literal else "wiki_prose"
    if not literal and re.search(
        r"\bspeculat\w*|\btheori[sz]\w*|\bmost likely\b|\blikely inspired\b|"
        r"\bmay be a nod\b|\bmay imply\b|\bit['’]s possible\b",
        block["text"],
        re.I,
    ):
        source_type = "speculation"
    return {
        "lang": lang,
        "source_type": source_type,
        "source_type_evidence": "literal_item_description_or_dialogue" if literal else "wiki_article_structure",
    }


def context_groups(section, html_lang, *, gameplay=False):
    def key(block):
        decision, reason = block_decision(section["section"], block, gameplay=gameplay)
        meta = block_metadata(block, html_lang)
        variant = block.get("variant_context") or {}
        return (
            decision,
            "source_infobox" if gameplay and block["kind"] in {"infobox", "infobox_stats"} else reason,
            meta["lang"],
            meta["source_type"],
            variant.get("anchor"),
            variant.get("label"),
            "infobox" if gameplay and block["kind"] in {"infobox", "infobox_stats"} else block["kind"],
        )

    return [list(group) for _, group in groupby(section["blocks"], key=key)]
