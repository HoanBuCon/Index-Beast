"""Conservative cell quality gates; preserve raw values and unresolved qualifiers."""

import re


def review_reason(value, row_key=""):
    if re.fullmatch(r"[-–—_]{2,}", value.strip()):
        return "decorative_source_separator"
    if re.search(r"\[\s*note\s+\d+\s*\]", value + " " + row_key, re.I):
        return "unresolved_source_note"
    return None
