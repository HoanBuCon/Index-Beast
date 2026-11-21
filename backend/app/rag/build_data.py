"""Eight-attribute allocation check: arithmetic always, weapon requirements when sourced. No damage maths.

Level accounting (attribute total = level + 79) comes from a curated, sourced snapshot in the knowledge pack
(`rule_data`). Starting-class values are quoted by the planner from the origin page in the corpus (all ten
origins are indexed; the default when the player names none is Wretch). Without quoted class values the
floors are reported unchecked; without a sourced weapon requirement the allocation is still shown, labelled
"requirements not checked". Extraction is not human verification.
"""

import copy
import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.rag.evidence import evidence_units
from app.rag.matching import name_key

ATTRIBUTES = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")
DEFAULT_CLASS = "Wretch"
# Validity bounds of the game, not cited facts (a sourced cap snapshot is still to be added; cần kiểm chứng).
ATTRIBUTE_CAP = 99
MAX_LEVEL = 713
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
# Game abbreviations as wikis print them ("Int: 36, Fth: 0, Arc: 0"). In prose they match only as
# "Str"/"STR": lowercase "end"/"int"/"arc" are ordinary words.
ATTRIBUTE_ABBREVIATIONS = {
    "vigor": ("vig",),
    "mind": ("mnd",),
    "endurance": ("end",),
    "strength": ("str",),
    "dexterity": ("dex",),
    "intelligence": ("int",),
    "faith": ("fai", "fth"),
    "arcane": ("arc",),
}
_NAME_TO_ATTRIBUTE = {
    **{n.casefold(): k for k, names in ATTRIBUTE_NAMES.items() for n in names},
    **{form: k for k, shorts in ATTRIBUTE_ABBREVIATIONS.items() for a in shorts for form in (a.title(), a.upper())},
}
_FULL = "|".join(sorted((re.escape(n) for names in ATTRIBUTE_NAMES.values() for n in names), key=len, reverse=True))
_SHORT = "|".join(f"{a.title()}|{a.upper()}" for shorts in ATTRIBUTE_ABBREVIATIONS.values() for a in shorts)


def attribute_surfaces(key: str) -> tuple[str, ...]:
    """English surfaces a source uses for one attribute: full name, then its abbreviations."""
    return (key, *ATTRIBUTE_ABBREVIATIONS[key])


def _names_only(label: str, key: str) -> bool:
    """A header such as "Required Str." or "Starting Vigor" names exactly this one attribute."""
    named = {
        name
        for word in re.findall(r"[a-z]+", label.casefold())
        for name in ATTRIBUTES
        if word in attribute_surfaces(name)
    }
    return named == {key}


_STAT_WORD = re.compile(rf"(?<!\w)(?:(?i:{_FULL})|{_SHORT})(?!\w)")
_STAT_NUMBER = re.compile(rf"{_STAT_WORD.pattern}\.?\s*[:=|—–-]?\s*\d")


_STAT_PAIR = re.compile(rf"({_STAT_WORD.pattern})\.?\s*[:=|—–-]?\s*(\d+)(?!\.\d)")


def _attribute(word: str) -> str | None:
    return _NAME_TO_ATTRIBUTE.get(word, _NAME_TO_ATTRIBUTE.get(word.casefold()))


def stat_pairs(text: str) -> list[tuple[str, int]]:
    """(attribute, number) pairs written in prose or Markdown tables: "Vigor 40", "Sức mạnh: 40",
    a row "| Vigor | 40 |", or a header row of attributes followed by a row of numbers."""
    pairs = [(_attribute(m.group(1)), int(m.group(2))) for m in _STAT_PAIR.finditer(text)]
    lines = text.splitlines()
    for i, line in enumerate(lines):
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")] if "|" in line else []
        names = [_attribute(c) for c in cells]
        if sum(n is not None for n in names) < 2:
            continue
        for row in lines[i + 1 :]:
            values = [c.strip().strip("*") for c in row.strip().strip("|").split("|")] if "|" in row else []
            if not values or all(re.fullmatch(r"[: -]*", v) for v in values):
                if values:
                    continue  # Markdown separator row
                break
            pairs += [(n, int(v)) for n, v in zip(names, values, strict=False) if n and re.fullmatch(r"\d+", v)]
            break
    return [p for p in pairs if p[0]]


def checked_numbers(artifact: dict) -> dict[str, set[int]]:
    """Numbers an answer may print per attribute: the checked allocation and the quoted floors/requirements."""
    data = artifact.get("data") or {}
    allowed = {k: {v} for k, v in artifact["allocation"].items()}
    for key, fact in (data.get("requirements") or {}).items():
        allowed[key].add(fact["value"])
    for key, fact in ((data.get("starting_class") or {}).get("base") or {}).items():
        allowed[key].add(fact["value"])
    return allowed


def unchecked_stat_pairs(text: str, artifact: dict) -> list[tuple[str, int]]:
    allowed = checked_numbers(artifact)
    return [(k, v) for k, v in stat_pairs(text) if v not in allowed.get(k, set())]


class Number(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int = Field(ge=0, le=10000)
    source_id: str
    quote_id: str
    label: str = Field(min_length=2, max_length=100)


class ClassData(BaseModel):
    """Starting values the planner quoted from an origin's corpus page (e.g. its Infobox "Level: 9 / Vigor: 15")."""

    model_config = ConfigDict(extra="forbid", strict=True)
    # Optional: defaults to the user's class, else Wretch (live 20/11: the model sent a non-string name twice).
    name: str | None = Field(default=None, min_length=2, max_length=60)
    level: Number
    base: dict[str, Number] = Field(min_length=8, max_length=8)


class BuildData(BaseModel):
    """What the planner adds to its allocation, all optional and all quoted from opened sources:
    the equipment with its minimum requirements, and the starting class with its starting values."""

    model_config = ConfigDict(extra="forbid", strict=True)
    weapon: str | None = Field(default=None, min_length=1, max_length=120)
    usage: Literal["one_handed_no_bonuses"] = "one_handed_no_bonuses"
    requirements: dict[str, Number] = Field(default_factory=dict, max_length=8)
    starting_class: ClassData | None = None


class CheckedBuild(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allocation: dict[str, int] = Field(min_length=8, max_length=8)
    data: BuildData
    weapon: str | None
    starting_class: str | None
    sources: list[str] = Field(min_length=1, max_length=8)
    rule_sources: list[str] = Field(min_length=1, max_length=1)
    class_sources: list[str] = Field(max_length=2)
    requirement_sources: list[str] = Field(max_length=5)
    profile: dict[str, Any]
    attribute_total: int
    class_floor_verified: bool
    class_assumed: bool
    weapon_suggested: bool
    requirements_checked: bool
    provenance: dict[str, dict[str, Any]]
    optimality_verified: bool
    review_status: str
    version: str = Field(pattern=r"^[0-9a-f]{64}$")


def level_rule():
    """The curated level accounting rule (total = level + offset) from the knowledge pack, as a citable hit."""
    from app.rag.gameplay_knowledge import load_pack
    from core.types import Hit

    for group in load_pack()["groups"]:
        for row in group["hits"]:
            if row["payload"].get("rule_kind") == "level_rule" and row["payload"].get("rule_data"):
                return Hit(row["id"], 0.0, copy.deepcopy(row["payload"])), row["payload"]["rule_data"]
    raise RuntimeError("Knowledge pack lacks the level accounting rule")


def target_level(profile) -> int | None:
    match = re.search(r"\d+", str(profile.get("level") or ""))
    return int(match.group()) if match else None


def build_rules(profile) -> dict | None:
    """Targets an allocation must meet, shown to the planner before it proposes numbers. None without a level.

    Class starting values are not built in: the planner quotes them from the class page in the corpus
    (the user's class, or the default Wretch). Without them the floors are reported unchecked.
    """
    level = target_level(profile)
    if level is None:
        return None
    hit, data = level_rule()
    return {
        "level": level,
        "attribute_total": level + data["level_offset"],
        "attribute_cap": ATTRIBUTE_CAP,
        "starting_class": profile.get("starting_class"),
        "default_class": DEFAULT_CLASS,
        "rule_sources": [hit.id],
    }


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


_PROVENANCE_KEYS = (
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


def _quote(fact, sources):
    hit = sources.get(fact.source_id)
    if hit is None:
        raise ValueError(f"Unknown source {fact.source_id}: open or search it first")
    quote = evidence_units(hit.payload["text"]).get(fact.quote_id)
    if quote is None:
        raise ValueError(f"Unknown quote ID {fact.quote_id} for {fact.source_id}")
    return quote.replace("**", "")


def _bound_attribute(key, fact, sources, what):
    quote = _quote(fact, sources)
    # The attribute is the dict key; the source must pair THAT attribute with the number, whatever header the
    # model copied ("Int: 36", "Intelligence: | 28 |", Infobox "Vigor: 15"). A label such as "Required Str."
    # or "Str Req" still binds when it names exactly this attribute.
    if not (
        any(bound_value(quote, s, fact.value) for s in attribute_surfaces(key))
        or (_names_only(fact.label, key) and bound_value(quote, fact.label, fact.value))
    ):
        raise ValueError(
            f"{what} {key} {fact.value} is not bound to its label/header in {fact.source_id} {fact.quote_id}"
            f' (expected a "{key.title()}" or "{attribute_surfaces(key)[1].title()}" label or column)'
        )


def _names(entity, ids, sources):
    return any(
        entity.casefold() in (sources[i].payload["title"] + " " + sources[i].payload["text"]).casefold() for i in ids
    )


def complete_allocation(allocation, fill, floors, total):
    """Deterministic arithmetic, the calculator's job: with `fill`, unset attributes take their floor and the
    `fill` attribute takes whatever is left of the level's total. Without `fill`, all eight must be given."""
    if any(k not in ATTRIBUTES for k in allocation) or any(type(v) is not int for v in allocation.values()):
        raise ValueError("Allocation keys must be the eight attributes with integer values")
    if not fill:
        if set(allocation) != set(ATTRIBUTES):
            raise ValueError("Give all eight attributes, or set fill to the attribute that takes the remainder")
        return dict(allocation)
    if fill not in ATTRIBUTES:
        raise ValueError("fill must be one of the eight attributes")
    if floors is None and set(allocation) | {fill} != set(ATTRIBUTES):
        # Without quoted class floors an unset attribute would fall to 1 (live 20/11: "Intelligence 1").
        raise ValueError(
            "Quote the starting class Infobox in build_data.starting_class (the user's class, or Wretch when none "
            "was named) so unset attributes take its floors, or give all eight numbers yourself"
        )
    floors = floors or dict.fromkeys(ATTRIBUTES, 1)
    complete = {k: allocation.get(k, floors[k]) for k in ATTRIBUTES if k != fill}
    remainder = total - sum(complete.values())
    if remainder < floors[fill]:
        raise ValueError(
            f"The other attributes already use {sum(complete.values())} of {total} points; {fill} would get "
            f"{remainder}, below its starting value {floors[fill]}. Lower some targets."
        )
    if remainder > ATTRIBUTE_CAP:
        raise ValueError(
            f"{fill} would get {remainder} (over {ATTRIBUTE_CAP}); raise other targets by {remainder - ATTRIBUTE_CAP}"
        )
    complete[fill] = remainder
    return {k: complete[k] for k in ATTRIBUTES}


def check(data, allocation, profile, hits, fill=None):
    """Validate a proposed eight-attribute allocation. Arithmetic is always checked; floors and requirements
    only when the planner quoted them from opened sources. No damage/AR/optimality is computed.
    With `fill`, the calculator completes a partial allocation (see complete_allocation).
    """
    rules = BuildData.model_validate(data or {})
    targets = build_rules(profile)
    if targets is None:
        raise ValueError("A target level is required for an allocation")
    level, offset = targets["level"], targets["attribute_total"] - targets["level"]
    if not 1 <= level <= MAX_LEVEL:
        raise ValueError("Unsupported target level")
    sources = {h.id: h for h in hits}
    # Equipment: a player-confirmed weapon must be used as given; otherwise the planner's pick is a suggestion.
    requested = profile.get("weapon")
    if requested and rules.weapon and name_key(rules.weapon) != name_key(requested):
        raise ValueError("Build data does not match the confirmed weapon")
    weapon = rules.weapon or requested
    if not set(rules.requirements) <= set(ATTRIBUTES):
        raise ValueError("Invalid attribute keys")
    if rules.requirements and not weapon:
        raise ValueError("Requirements need the weapon they belong to")
    for key, fact in rules.requirements.items():
        _bound_attribute(key, fact, sources, "Requirement")
    requirement_sources = sorted({fact.source_id for fact in rules.requirements.values()})
    if len(requirement_sources) > 5:
        raise ValueError("Requirements need at most five sources")
    if requirement_sources and not _names(weapon, requirement_sources, sources):
        raise ValueError("Requirement source does not name the weapon")
    # Class: a player-confirmed class must be used as given; without one the planner may quote the default.
    named = profile.get("starting_class")
    origin = rules.starting_class
    class_sources = []
    if origin is not None and origin.name is None:
        origin = origin.model_copy(update={"name": named or DEFAULT_CLASS})
    if origin is not None:
        if named and name_key(origin.name) != name_key(named):
            raise ValueError("Class data does not match the confirmed class")
        if set(origin.base) != set(ATTRIBUTES):
            raise ValueError("Class data needs all eight starting attributes")
        for key, fact in origin.base.items():
            _bound_attribute(key, fact, sources, f"{origin.name} starting")
        if not bound_value(_quote(origin.level, sources), "Level", origin.level.value) and not bound_value(
            _quote(origin.level, sources), origin.level.label, origin.level.value
        ):
            raise ValueError(f"{origin.name} starting level {origin.level.value} is not bound to its label")
        class_sources = sorted({f.source_id for f in [origin.level, *origin.base.values()]})
        if len(class_sources) > 2 or not _names(origin.name, class_sources, sources):
            raise ValueError("Class source does not name the class")
        if sum(f.value for f in origin.base.values()) != origin.level.value + offset:
            # Every origin starts with level + 79 points; a mismatch means a misread value.
            raise ValueError(f"{origin.name} starting values do not sum to its level + {offset}; re-read them")
        if level < origin.level.value:
            raise ValueError(f"Level {level} is below the {origin.name} starting level {origin.level.value}")
    references = [*requirement_sources, *class_sources]
    # Do not mix explicitly different releases/patches; unknown remains an uncertainty.
    for key in ("game_scope", "release_scope", "patch_version", "game_version", "upgrade_level", "affinity"):
        known = {
            json.dumps(sources[i].payload[key], sort_keys=True, ensure_ascii=False)
            for i in requirement_sources
            if key in sources[i].payload
            and sources[i].payload[key] not in (None, "unknown", "base_candidate", "sote_candidate")
        }
        if len(known) > 1:
            raise ValueError("Conflicting requirement conditions")
    if any(sources[i].payload.get("handedness") in ("two_handed", "two-handed") for i in requirement_sources):
        raise ValueError("Two-handed evidence cannot validate a one-handed allocation")
    total = targets["attribute_total"]
    floors = {k: f.value for k, f in origin.base.items()} if origin else dict.fromkeys(ATTRIBUTES, 1)
    class_name = origin.name if origin else named
    allocation = complete_allocation(allocation, fill, floors if origin else None, total)
    if sum(allocation.values()) != total:
        raise ValueError(
            f"Allocation sums to {sum(allocation.values())}; level {level} needs exactly {total} attribute points"
            " (or set fill to one attribute and let the calculator add the remainder)"
        )
    problems = []
    for key in ATTRIBUTES:
        value = allocation[key]
        if value < floors[key]:
            problems.append(f"{key} {value} is below the {class_name} starting value {floors[key]}")
        if value > ATTRIBUTE_CAP:
            problems.append(f"{key} {value} exceeds {ATTRIBUTE_CAP}")
        if key in rules.requirements and value < rules.requirements[key].value:
            problems.append(f"{key} {value} is below the {weapon} requirement {rules.requirements[key].value}")
    if problems:
        # Specific, so the planner can correct the numbers in one more call.
        raise ValueError("; ".join(problems))
    rule_hit, _ = level_rule()
    every = {rule_hit.id: rule_hit, **{i: sources[i] for i in references}}
    artifact = {
        "allocation": dict(allocation),
        "data": rules.model_dump(exclude_none=True),
        "weapon": weapon,
        "starting_class": class_name,
        "sources": list(dict.fromkeys([rule_hit.id, *class_sources, *requirement_sources])),
        "rule_sources": [rule_hit.id],
        "class_sources": class_sources,
        "requirement_sources": requirement_sources,
        "profile": dict(profile),
        "attribute_total": total,
        "class_floor_verified": origin is not None,
        "class_assumed": origin is not None and not named,
        "weapon_suggested": bool(rules.weapon) and not requested,
        "requirements_checked": bool(rules.requirements),
        "provenance": {
            i: {k: hit.payload[k] for k in _PROVENANCE_KEYS if k in hit.payload} for i, hit in every.items()
        },
        "optimality_verified": False,
        "review_status": "runtime_extraction_not_human_reviewed",
    }
    artifact["version"] = hashlib.sha256(json.dumps(artifact, sort_keys=True).encode()).hexdigest()
    return CheckedBuild.model_validate(artifact).model_dump()
