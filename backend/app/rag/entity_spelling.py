"""Conservative typo matching against names returned by the local corpus."""

import re
import unicodedata

from app.rag.rewrite import name_key, preserves_numbers


def spelling_key(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", name_key(text)) if not unicodedata.combining(c))


def close_spelling(raw: str, candidate: str) -> bool:
    a, b = spelling_key(raw), spelling_key(candidate)
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and not any(c.isdecimal() for c in a + b):
        repeated_letters = r"([^\W\d_])\1+"
        if a.replace(" ", "") == b.replace(" ", "") or (
            len(a) > len(b) and re.sub(repeated_letters, r"\1", a) == re.sub(repeated_letters, r"\1", b)
        ):
            return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1 or any(c.isdecimal() for c in a + b):
        return False
    i = next((i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y), min(len(a), len(b)))
    if len(a) == len(b):
        return a[i + 1 :] == b[i + 1 :] or (a[i : i + 2] == b[i : i + 2][::-1] and a[i + 2 :] == b[i + 2 :])
    longer, shorter = (a, b) if len(a) > len(b) else (b, a)
    return longer[i + 1 :] == shorter[i:]


def matching_names(raw, hits):
    exact, close, partial = {}, {}, {}
    typed_words = name_key(raw).split()
    for hit in hits:
        title = hit.payload.get("title")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not (preserves_numbers(raw, title) and preserves_numbers(title, raw))
        ):
            continue
        aliases = hit.payload.get("aliases")
        forms = [title, *aliases] if isinstance(aliases, list) else [title]
        names = [s for s in forms if isinstance(s, str)]
        bucket = exact if any(name_key(raw) == name_key(s) for s in names) else close
        if bucket is exact or any(close_spelling(raw, s) for s in names):
            bucket.setdefault(name_key(title), (title, []))[1].append(hit)
        elif len(typed_words) >= 2 and all(word in name_key(title).split() for word in typed_words):
            partial.setdefault(name_key(title), (title, []))[1].append(hit)
    # A partial title provides options for clarification, never grounds an automatic correction.
    return list((exact or close or partial).values()), bool(exact or close)


def correct_name(text: str, raw: str, canonical: str) -> str:
    parts = re.split(r"[\s,]+", raw.strip())
    pattern = r"(?<!\w)" + r"(?:\s*,\s*|\s+)".join(map(re.escape, parts)) + r"(?!\w)"
    return re.sub(pattern, lambda _: canonical, text, flags=re.I)
