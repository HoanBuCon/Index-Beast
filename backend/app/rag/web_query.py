"""Deterministic domain anchoring; preserves the whole request, no guessed entities."""

import re

from app.rag.overview import folded


def web_query(query: str) -> tuple[str, str]:
    text = folded(query)
    anchor = "" if "elden ring" in text else "Elden Ring\n"
    # This recognizes an intent, not a factual answer or a nickname-to-entity mapping.
    classes = re.search(r"\b(class|classes|lop nhan vat)\b", text)
    starting = re.search(r"\b(khoi dau|bat dau|starting|starter|initial|character creation)\b", text)
    if classes and starting:
        return anchor + query + "\nSearch focus: starting classes list character creation", "starting_classes"
    return anchor + query, "domain_anchor" if anchor else "preserved"
