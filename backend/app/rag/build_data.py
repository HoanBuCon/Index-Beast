"""Sourced numerical inputs and deterministic feasibility. Extraction is not human verification."""

import copy
import hashlib
import json
import re
import time
from collections import OrderedDict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.rag.build_math import ATTRIBUTES
from app.rag.evidence import evidence_units


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
    starting_class: str
    weapon: str
    usage: str = Field(pattern="^one_handed_no_bonuses$")
    starting_level: Number
    base: dict[str, Number] = Field(min_length=8, max_length=8)
    requirements: dict[str, Number] = Field(min_length=1, max_length=8)
    points_per_level: Number
    attribute_cap: Number
    class_floor_rule: Rule


class CheckedBuild(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allocation: dict[str, int] = Field(min_length=8, max_length=8)
    data: BuildData
    sources: list[str] = Field(min_length=1, max_length=5)
    profile: dict[str, Any]
    attribute_total: int
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
        key = (data["starting_class"], data["weapon"], data["usage"])
        self.entries[key] = (time.monotonic(), copy.deepcopy(data), copy.deepcopy(hits))
        self.entries.move_to_end(key)
        while len(self.entries) > 32:
            self.entries.popitem(last=False)

    def get(self, profile):
        key = (profile.get("starting_class"), profile.get("weapon"), "one_handed_no_bonuses")
        item = self.entries.get(key)
        if item is None or time.monotonic() - item[0] > 3600:
            self.entries.pop(key, None)
            return None
        return copy.deepcopy(item[1:])


def check(data, allocation, profile, hits):
    rules = BuildData.model_validate(data)
    if rules.starting_class != profile.get("starting_class") or rules.weapon != profile.get("weapon"):
        raise ValueError("Build data does not match confirmed class/weapon")
    if set(rules.base) != set(ATTRIBUTES) or not set(rules.requirements) <= set(ATTRIBUTES):
        raise ValueError("Invalid attribute keys")
    for key, fact in [*rules.base.items(), *rules.requirements.items()]:
        abbreviation = dict(zip(ATTRIBUTES, ("vig", "mnd", "end", "str", "dex", "int", "fai", "arc"), strict=True))[key]
        if fact.label.casefold().removeprefix("required ").removeprefix("starting ") not in {key, abbreviation}:
            raise ValueError("Numeric header does not identify requested attribute")
    sources = {h.id: h for h in hits}
    references = set()
    facts = [
        rules.starting_level,
        rules.points_per_level,
        rules.attribute_cap,
        *rules.base.values(),
        *rules.requirements.values(),
    ]
    for fact in facts:
        hit = sources.get(fact.source_id)
        if hit is None:
            raise ValueError("Unknown numeric source")
        quote = evidence_units(hit.payload["text"]).get(fact.quote_id)
        # Preserve headers/labels and exact integer. Do not parse a free-floating table number.
        entity = (
            rules.starting_class
            if fact is rules.starting_level or any(fact is f for f in rules.base.values())
            else None
        )
        if quote is None or not bound_value(quote.replace("**", ""), fact.label, fact.value, entity=entity):
            raise ValueError("Numeric value is not bound to source label/header")
        references.add(fact.source_id)
    floor = rules.class_floor_rule
    if floor.source_id not in sources or floor.quote not in evidence_units(
        sources[floor.source_id].payload["text"]
    ).get(floor.quote_id, ""):
        raise ValueError("Missing class floor/respec rule evidence")
    references.add(floor.source_id)
    if not 1 <= len(references) <= 5:
        raise ValueError("Accounting requires at most five original sources")
    for entity in (rules.starting_class, rules.weapon):
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
    if level < rules.starting_level.value or rules.points_per_level.value != 1:
        raise ValueError("Unsupported target level/progression")
    if set(allocation) != set(ATTRIBUTES) or any(type(v) is not int for v in allocation.values()):
        raise ValueError("Invalid allocation")
    expected = sum(f.value for f in rules.base.values()) + level - rules.starting_level.value
    if sum(allocation.values()) != expected:
        raise ValueError("Incorrect attribute total")
    for key, value in allocation.items():
        if value < rules.base[key].value or value > rules.attribute_cap.value:
            raise ValueError("Class floor or cap violated")
        if value < rules.requirements.get(key, rules.base[key]).value:
            raise ValueError("One-handed requirements not met")
    artifact = {
        "allocation": dict(allocation),
        "data": rules.model_dump(),
        "sources": sorted(references),
        "profile": dict(profile),
        "attribute_total": expected,
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
    return CheckedBuild.model_validate(artifact).model_dump()
