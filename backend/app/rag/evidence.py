"""Deterministic evidence IDs: server extracts exact source substrings, never fuzzy-matches model prose."""


def evidence_units(text: str) -> dict[str, str]:
    if 8 <= len(text) <= 2000:
        return {"q0": text}
    units, start = {}, 0
    while start < len(text):
        end = min(start + 2000, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start + 1000, end), text.rfind(". ", start + 1000, end))
            if boundary > start:
                end = boundary + 1
        fragment = text[start:end].strip()
        if len(fragment) >= 8:
            units[f"q{len(units) + 1}"] = fragment
        start = end
    return units
