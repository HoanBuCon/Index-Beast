"""Evidence rules for the wiki cohort and spoiler-aware chunk payload."""

import re

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
EXTERNAL = re.compile(r"^(?:elden ring\s*:?\s*)?(?:nightreign|tarnished edition)$", re.I)
ORIGIN_LEAD = re.compile(r"[^.\n]+ is one of the starting origins in ELDEN RING \(2022\)\.", re.I)
REGION_LEAD = re.compile(
    r"[^.\n]+ is (?:a region in the Lands Between|a sub-region (?:of|in|located in) Limgrave|"
    r"a (?:location|ruin) in ELDEN RING \(2022\))\.",
    re.I,
)


def wiki_context(raw, doc):
    categories = sorted({s.replace("_", " ") for s in raw["categories"]})
    # Edition names mentioned inside an Elden Ring article do not change its game identity.
    excluded = EXTERNAL.fullmatch(doc["title"].strip())
    return {
        "game_scope": "out_of_scope" if excluded else "elden_ring",
        "game_scope_reason": "external_title" if excluded else "accepted_wikigg_elden_ring_cohort",
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
