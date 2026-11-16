"""Evidence rules for the wiki cohort and spoiler-aware chunk payload."""

import re

from bs4 import BeautifulSoup

VERSION = "tv2-spoiler-1"
EARLY_LOCATIONS = {
    "limgrave",
    "weeping peninsula",
    "stranded graveyard",
    "stormhill",
    "church of elleh",
    "gatefront ruins",
}
BASIC_TUTORIALS = {
    "about guarding",
    "about guard counters",
    "about dodging",
    "about death",
    "about the map",
    "about sites of grace",
    "about item crafting",
    "about skills",
    "about the cave of knowledge",
    "about summoning pools",
    "about crouching",
    "about wielding armaments",
    "about pouches",
}
LATE = re.compile(
    r"\b(?:leyndell,? ashen capital|crumbling farum azula|mountaintops of the giants|"
    r"consecrated snowfield|miquella.s haligtree|elfael|enir-ilim|final boss|"
    r"age of (?:the )?stars ending|lord of (?:the )?frenzied flame ending|"
    r"age of fracture|age of order|age of duskborn|blessing of despair)\b",
    re.I,
)
ENDING = re.compile(
    r"\b(?:endings?|epilogues?|finale)\b|\b(?:unlock|achieve|trigger|obtain)\b[^.!?\n]{0,90}\bending\b",
    re.I,
)
PROGRESSION = re.compile(r"quest|dialogue|lore|history|story|acquisition|walkthrough", re.I)
DLC = re.compile(r"shadow of the erdtree|realm of shadow", re.I)
EXTERNAL = re.compile(r"^(?:elden ring\s*:?\s*)?(?:nightreign|tarnished edition|tarnished pack)$", re.I)
TARNISHED_MARKER = re.compile(r"tarnished|TP\.webp", re.I)
TARNISHED_EXCLUSIVE = re.compile(
    r"\b(?:exclusive to|only appears in|only available in|only obtainable in|it was introduced with)\b.{0,120}"
    r"\b(?:elden ring\s+)?tarnished (?:edition|pack)\b|"
    r"\btarnished (?:edition|pack)\b.{0,120}\b(?:exclusive|only appears|only available|only obtainable)\b",
    re.I,
)
ARMOR_ARTICLE = re.compile(r"\b(?:is|are) an armor (?:piece|set)\b", re.I)
TARNISHED_BADGE = 'a[title="Tarnished Pack"] img[src*="TP.webp"]'
OUT_OF_SCOPE_REASONS = frozenset({"external_title", "external_tarnished_edition_content"})
ORIGIN_LEAD = re.compile(r"[^.\n]+ is one of the starting origins in ELDEN RING \(2022\)\.", re.I)
REGION_LEAD = re.compile(
    r"[^.\n]+ is (?:a region in the Lands Between|a sub-region (?:of|in|located in) Limgrave|"
    r"a (?:location|ruin) in ELDEN RING \(2022\))\.",
    re.I,
)


def _tarnished_exclusive(content):
    if not TARNISHED_MARKER.search(content):
        return False
    soup = BeautifulSoup(content, "html.parser")
    body = soup.select_one(".mw-parser-output, #page-content, main") or soup
    lead = next((p for p in body.find_all("p") if p.get_text(strip=True)), None)
    if lead is None:
        return False
    text = lead.get_text(" ", strip=True)
    if TARNISHED_EXCLUSIVE.search(text) or (
        re.search(r"\bit is exclusive to\b", text, re.I) and lead.select_one(TARNISHED_BADGE)
    ):
        return True
    # Equipment links in a skill's Acquisition section mark individual items.
    if not ARMOR_ARTICLE.search(text):
        return False
    if body.select_one('.portable-infobox img[src*="TP.webp"]'):
        return True
    headline = body.select_one("h2 .mw-headline#Acquisition")
    if headline is None:
        return False
    for sibling in headline.find_parent("h2").find_next_siblings():
        if sibling.name == "h2":
            break
        if sibling.select_one(TARNISHED_BADGE):
            return True
    return False


def wiki_context(raw, doc):
    categories = sorted({s.replace("_", " ") for s in raw["categories"]})
    reason = "accepted_wikigg_elden_ring_cohort"
    if EXTERNAL.fullmatch(doc["title"].strip()):
        reason = "external_title"
    elif _tarnished_exclusive(raw.get("content", "")):
        reason = "external_tarnished_edition_content"
    return {
        "game_scope": "out_of_scope" if reason in OUT_OF_SCOPE_REASONS else "elden_ring",
        "game_scope_reason": reason,
        "wiki_categories": categories,
        "spoiler_rule_version": VERSION,
    }


def spoiler(doc, section, unit):
    """Rate the full source unit so a split cannot hide context from the classifier."""
    title, heading = doc["title"], section["section"]
    text = unit["text"]
    categories = doc["wiki_categories"]
    context = "\n".join(
        (title, heading, (section.get("variant_context") or {}).get("label") or "", unit.get("trigger") or "", text)
    )
    if ENDING.search(title) or ENDING.search(heading) or any(ENDING.search(c) for c in categories):
        return 2, "ending_title_heading_or_category"
    if LATE.search(context) or re.search(r"\b(?:the|this|an|each) ending\b", context, re.I):
        return 2, "late_area_or_ending_in_unit"
    if (
        DLC.search(context)
        or any(DLC.search(c) for c in categories)
        or doc["release_scope"] in {"sote_candidate", "mixed_or_sote_candidate"}
    ):
        return 1, "sote_or_mixed_context"
    if PROGRESSION.search(heading) or unit.get("quest_stage") or unit.get("trigger"):
        return 1, "progression_context"
    if unit["lang"] == "en":
        if "Origins" in categories:
            if heading == "Introduction" and ORIGIN_LEAD.fullmatch(text):
                return 0, "starting_origin_definition"
            if heading == "Starting equipment" and text.startswith("Armaments\n") and "\nGear\n" in text:
                return 0, "starting_origin_inventory"
        if (
            heading == "Introduction"
            and title.casefold() in EARLY_LOCATIONS
            and "Locations" in categories
            and REGION_LEAD.fullmatch(text)
        ):
            return 0, "early_region_definition"
        if (
            heading in {"Introduction", "Description"}
            and "Tutorials" in categories
            and "Unused Content" not in categories
            and title.casefold() in BASIC_TUTORIALS
            and not PROGRESSION.search(text)
        ):
            return 0, "basic_controls_tutorial"
    return 1, "safety_not_established"
