"""Provenance text matching only: does a user-supplied surface/number appear in a text?

No keyword lists, entity dictionaries, intent rules or NER. Semantic decisions belong to the Agent.
"""

import re
import unicodedata
from collections import Counter


def folded(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold()).replace("đ", "d")
    return " ".join(re.sub(r"[^\w\s]", " ", "".join(c for c in text if not unicodedata.combining(c))).split())


def preserves_numbers(question: str, query: str) -> bool:
    """Every numeric literal of the first text (level, stat, upgrade, patch) remains in the second."""
    pattern = r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)"
    expected = Counter(re.findall(pattern, question))
    actual = Counter(re.findall(pattern, query))
    return all(actual[number] >= count for number, count in expected.items())


def _normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().replace("’", "'")


def contains_text(text: str, surface: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(_normalized(surface)) + r"(?!\w)", _normalized(text)) is not None


def name_key(text: str) -> str:
    return " ".join(re.sub(r"(?<=[^\W\d_]),\s*(?=[^\W\d_])", " ", _normalized(text)).split())


def contains_name(text: str, name: str) -> bool:
    key = name_key(name)
    return bool(key and re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", name_key(text)))
