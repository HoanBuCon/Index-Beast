"""Unicode/whitespace normalization without translating or rewriting source text."""

import re
import unicodedata


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value).replace("\xa0", " ").replace("\u200b", "")
    return "\n".join(line for row in value.splitlines() if (line := re.sub(r"[^\S\n]+", " ", row).strip()))


def normalized_key(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(value)).strip(" “”—|")
