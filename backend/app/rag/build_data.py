"""Sourced numerical inputs and deterministic feasibility. Extraction is not human verification.

Every class shares the same level accounting (attribute total = level + a sourced offset); a starting class
only sets per-attribute floors. A class is therefore optional: without it the floors are reported unverified.
When the player names no class or weapon, the planner may use a sourced default class (e.g. Wretch, all tens)
and suggest equipment; the artifact marks both as assumptions, never as player-confirmed facts.
"""

import copy
import hashlib
import json
import re
import time
from collections import OrderedDict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.rag.evidence import evidence_units

ATTRIBUTES = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")
# Surface names of the eight attributes (English, common abbreviations, Vietnamese). One table, used to keep
# unchecked per-attribute numbers out of model prose; it never decides what the player asked for.
ATTRIBUTE_NAMES = {
    "vigor": ("vigor", "sinh lực"),
    "mind": ("mind", "tâm trí", "tinh thần"),
    "endurance": ("endurance", "sức bền", "bền bỉ"),
    "strength": ("strength", "sức mạnh"),
    "dexterity": ("dexterity", "khéo léo", "nhanh nhẹn"),
    "intelligence": ("intelligence", "trí tuệ", "trí lực", "trí thông minh"),
    "faith": ("faith", "đức tin", "niềm tin"),
    "arcane": ("arcane", "huyền bí", "bí thuật"),
}
# Abbreviations match only as "Str"/"STR": lowercase "end"/"int"/"arc" are ordinary words in prose.
ATTRIBUTE_ABBREVIATIONS = dict(zip(ATTRIBUTES, ("vig", "mnd", "end", "str", "dex", "int", "fai", "arc"), strict=True))
_NAME_TO_ATTRIBUTE = {
    **{n.casefold(): k for k, names in ATTRIBUTE_NAMES.items() for n in names},
    **{form: k for k, a in ATTRIBUTE_ABBREVIATIONS.items() for form in (a.title(), a.upper())},
}
_FULL = "|".join(sorted((re.escape(n) for names in ATTRIBUTE_NAMES.values() for n in names), key=len, reverse=True))
_SHORT = "|".join(f"{a.title()}|{a.upper()}" for a in ATTRIBUTE_ABBREVIATIONS.values())
_STAT_WORD = re.compile(rf"(?<!\w)(?:(?i:{_FULL})|{_SHORT})(?!\w)")
_STAT_NUMBER = re.compile(rf"{_STAT_WORD.pattern}\.?\s*[:=|—–-]?\s*\d")


def stat_numbers_in(text: str) -> bool:
    """True if prose pairs an attribute with a number ("Str 40", "Sức mạnh: 40") or tabulates attributes."""
    if _STAT_NUMBER.search(text):
        return True
    return any(
        "|" in line
        and len({_NAME_TO_ATTRIBUTE.get(m, _NAME_TO_ATTRIBUTE.get(m.casefold())) for m in _STAT_WORD.findall(line)})
        >= 2
        for line in text.splitlines()
    )


class Number(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int = Field(ge=0, le=10000)
    source_id: str
    quote_id: str
    label: str = Field(min_length=2, max_length=100)


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str
    quote_id: str
    quote: str = Field(min_length=8, max_length=2000)


class BuildData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    weapon: str
    usage: str = Field(pattern="^one_handed_no_bonuses$")
    requirements: dict[str, Number] = Field(min_length=1, max_length=8)
    attribute_cap: Number
    # Class-independent accounting: target total = level + attribute_offset (e.g. "minus 79").
    attribute_offset: Number | None = None
    # Optional class floors. All four are supplied together, or none.
    starting_class: str | None = None
    starting_level: Number | None = None
    base: dict[str, Number] | None = Field(default=None, min_length=8, max_length=8)
    points_per_level: Number | None = None
    class_floor_rule: Rule | None = None

    def with_class(self) -> bool:
        parts = (self.starting_class, self.starting_level, self.base, self.points_per_level, self.class_floor_rule)
        if all(part is None for part in parts):
            return False
        if any(part is None for part in parts):
            raise ValueError(
                "Class data requires starting_class, starting_level, base, points_per_level and floor rule"
            )
        return True


class CheckedBuild(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allocation: dict[str, int] = Field(min_length=8, max_length=8)
    data: BuildData
    sources: list[str] = Field(min_length=1, max_length=5)
    profile: dict[str, Any]
    attribute_total: int
    class_floor_verified: bool
    class_assumed: bool
    weapon_suggested: bool
    units: dict[str, str]
    provenance: dict[str, dict[str, Any]]
    optimality_verified: bool
    review_status: str
    version: str = Field(pattern=r"^[0-9a-f]{64}$")


def bound_value(quote, label, value, *, entity=None):
    """Check lexical label/value binding, including aligned Markdown columns, not entailment."""
    # Tavily may preserve rendered image labels inside a table cell. Remove only that
    # decoration for binding; retain the original quote and headers in the artifact.
    quote = re.sub(r"(?:Collapse)?Image \d+: [^|\n]*?\.(?:png|jpe?g|webp)", "", quote, flags=re.I)
    direct = re.compile(rf"(?<!\w){re.escape(label)}\s*(?:[:=|—–-]\s*)*{value}(?!\w|\.\d)", re.I)
    if direct.search(quote):
        return True
    lines = quote.splitlines()
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        headers = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        columns = [n for n, h in enumerate(headers) if h.casefold() == label.casefold()]
        if len(columns) != 1:
            continue
        for row in lines[i + 1 :]:
            if "|" not in row:
                break
            cells = [c.strip().strip("*") for c in row.strip().strip("|").split("|")]
            if all(re.fullmatch(r"[: -]+", c or " ") for c in cells):
                continue
            if len(cells) != len(headers) or (entity and not any(entity.casefold() == c.casefold() for c in cells)):
                continue
            if cells[columns[0]] == str(value):
                return True
    return False


class BuildCache:
    """Per-pipeline public factual inputs only, 32 entries / one-hour TTL. Never player profiles."""

    def __init__(self):
        self.entries = OrderedDict()

    def put(self, data, hits):
        key = (data.get("starting_class") or "", data["weapon"], data["usage"])
        self.entries[key] = (time.monotonic(), copy.deepcopy(data), copy.deepcopy(hits))
        self.entries.move_to_end(key)
        while len(self.entries) > 32:
            self.entries.popitem(last=False)

    def get(self, profile):
        key = (profile.get("starting_class") or "", profile.get("weapon"), "one_handed_no_bonuses")
        item = self.entries.get(key)
        if item is None or time.monotonic() - item[0] > 3600:
            self.entries.pop(key, None)
            return None
        return copy.deepcopy(item[1:])


def check(data, allocation, profile, hits):
    rules = BuildData.model_validate(data)
    with_class = rules.with_class()
    # A player-confirmed value must be used as given; an absent one may be a sourced assumption/suggestion.
    weapon_suggested = not profile.get("weapon")
    if not weapon_suggested and rules.weapon != profile.get("weapon"):
        raise ValueError("Build data does not match the confirmed weapon")
    class_assumed = with_class and not profile.get("starting_class")
    if with_class and not class_assumed and rules.starting_class != profile.get("starting_class"):
        raise ValueError("Build data does not match the confirmed class")
    if not with_class and rules.attribute_offset is None:
        raise ValueError(
            "Without class data, supply attribute_offset from the level accounting rule "
            '(e.g. {"value": 79, "label": "minus"} for "level equals the sum ... minus 79")'
        )
    base = rules.base or {}
    if (with_class and set(base) != set(ATTRIBUTES)) or not set(rules.requirements) <= set(ATTRIBUTES):
        raise ValueError("Invalid attribute keys")
    for key, fact in [*base.items(), *rules.requirements.items()]:
        abbreviation = ATTRIBUTE_ABBREVIATIONS[key]
        # Headers such as "Required Str.", "Str Req" or "Starting Vigor" name exactly one attribute.
        named = {
            name
            for word in re.findall(r"[a-z]+", fact.label.casefold())
            for name, short in ATTRIBUTE_ABBREVIATIONS.items()
            if word in {name, short}
        }
        if named != {key}:
            raise ValueError(
                f"Numeric header does not identify {key}: label must contain exactly one attribute name, e.g. "
                f'"{key.title()}" or "Required {abbreviation.title()}"'
            )
    sources = {h.id: h for h in hits}
    references = set()
    facts = [
        fact
        for fact in (rules.starting_level, rules.points_per_level, rules.attribute_cap, rules.attribute_offset)
        if fact is not None
    ]
    facts += [*base.values(), *rules.requirements.values()]
    for fact in facts:
        hit = sources.get(fact.source_id)
        if hit is None:
            raise ValueError("Unknown numeric source")
        quote = evidence_units(hit.payload["text"]).get(fact.quote_id)
        # Preserve headers/labels and exact integer. Do not parse a free-floating table number.
        entity = rules.starting_class if fact is rules.starting_level or any(fact is f for f in base.values()) else None
        if quote is None or not bound_value(quote.replace("**", ""), fact.label, fact.value, entity=entity):
            raise ValueError("Numeric value is not bound to source label/header")
        references.add(fact.source_id)
    if with_class:
        floor = rules.class_floor_rule
        if floor.source_id not in sources or floor.quote not in evidence_units(
            sources[floor.source_id].payload["text"]
        ).get(floor.quote_id, ""):
            raise ValueError("Missing class floor/respec rule evidence")
        references.add(floor.source_id)
    if not 1 <= len(references) <= 5:
        raise ValueError("Accounting requires at most five original sources")
    for entity in (e for e in (rules.starting_class, rules.weapon) if e):
        if not any(entity.casefold() in (h.payload["title"] + " " + h.payload["text"]).casefold() for h in hits):
            raise ValueError("Entity not established in evidence")
    # Do not mix explicitly different releases/patches; unknown remains an uncertainty.
    condition_keys = (
        "game_scope",
        "release_scope",
        "patch_version",
        "game_version",
        "upgrade_level",
        "affinity",
        "ng_cycle",
        "variant_context",
        "handedness",
    )
    for key in condition_keys:
        known = {
            json.dumps(sources[i].payload[key], sort_keys=True, ensure_ascii=False)
            for i in references
            if key in sources[i].payload
            and sources[i].payload[key] not in (None, "unknown", "base_candidate", "sote_candidate")
        }
        if len(known) > 1:
            raise ValueError("Conflicting accounting conditions")
    if any(sources[i].payload.get("handedness") in ("two_handed", "two-handed") for i in references):
        raise ValueError("Two-handed evidence cannot validate a one-handed allocation")
    level = int(profile.get("level", "0"))
    if set(allocation) != set(ATTRIBUTES) or any(type(v) is not int for v in allocation.values()):
        raise ValueError("Invalid allocation")
    if with_class:
        if level < rules.starting_level.value or rules.points_per_level.value != 1:
            raise ValueError("Unsupported target level/progression")
        expected = sum(f.value for f in base.values()) + level - rules.starting_level.value
        if rules.attribute_offset is not None and expected != level + rules.attribute_offset.value:
            raise ValueError("Class data conflicts with level accounting")
    else:
        if not 1 <= level <= 713:
            raise ValueError("Unsupported target level")
        expected = level + rules.attribute_offset.value
    if sum(allocation.values()) != expected:
        raise ValueError("Incorrect attribute total")
    for key, value in allocation.items():
        floor_value = base[key].value if with_class else 1
        if value < floor_value or value > rules.attribute_cap.value:
            raise ValueError("Class floor or cap violated")
        if key in rules.requirements and value < rules.requirements[key].value:
            raise ValueError("One-handed requirements not met")
    artifact = {
        "allocation": dict(allocation),
        "data": rules.model_dump(exclude_none=True),
        "sources": sorted(references),
        "profile": dict(profile),
        "attribute_total": expected,
        "class_floor_verified": with_class,
        "class_assumed": class_assumed,
        "weapon_suggested": weapon_suggested,
        "units": {"allocation": "attribute_points", "starting_level": "level", "points_per_level": "points/level"},
        "provenance": {
            i: {
                k: sources[i].payload[k]
                for k in (
                    "url",
                    "retrieved_at",
                    "source_updated_at",
                    "game_scope",
                    "release_scope",
                    "patch_version",
                    "game_version",
                    "upgrade_level",
                    "affinity",
                    "ng_cycle",
                    "variant_context",
                    "handedness",
                    "review_status",
                    "source_type",
                )
                if k in sources[i].payload
            }
            for i in sorted(references)
        },
        "optimality_verified": False,
        "review_status": "runtime_extraction_not_human_reviewed",
    }
    artifact["version"] = hashlib.sha256(json.dumps(artifact, sort_keys=True).encode()).hexdigest()
    checked = CheckedBuild.model_validate(artifact).model_dump()
    checked["data"] = {k: v for k, v in checked["data"].items() if v is not None}  # Same shape as the input.
    return checked
