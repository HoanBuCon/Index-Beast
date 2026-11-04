"""Feasibility only, NOT optimization, damage or patch verification."""

import re

ATTRIBUTES = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")
SAMURAI = dict(zip(ATTRIBUTES, (12, 11, 13, 12, 15, 9, 8, 8), strict=True))
MOONVEIL = {"strength": 12, "dexterity": 18, "intelligence": 23}


def arithmetic_only(text):
    from app.rag.overview import folded

    text = folded(text)
    return bool(
        re.search(r"sum|total|minus|tong|khop", text)
        and re.search(r"attribute|stat|chi so", text)
        and not re.search(r"\bbuild\b|allocate|chia|phan bo", text)
    )


def check_allocation(values, profile):
    if profile.get("starting_class") != "Samurai" or profile.get("weapon") != "Moonveil":
        raise ValueError("Only checked Samurai/Moonveil rules are available")
    level = int(profile.get("level", "0"))
    if not 9 <= level <= 713 or set(values) != set(ATTRIBUTES):
        raise ValueError("Invalid target level or attribute keys")
    if any(type(value) is not int or not SAMURAI[key] <= value <= 99 for key, value in values.items()):
        raise ValueError("Below starting values, wrong type or above attribute cap")
    if sum(values.values()) != level + 79:
        raise ValueError("Attribute total does not match target level")
    if any(values[key] < minimum for key, minimum in MOONVEIL.items()):
        raise ValueError("One-handed weapon requirements not met")
    return {
        "target_level": level,
        "attribute_total": sum(values.values()),
        "feasible": True,
        "optimality_verified": False,
    }
