"""Conservative typo matching against names returned by retrieval."""

import re
import unicodedata

from app.rag.rewrite import contains_name, name_key, preserves_numbers


def spelling_key(text: str) -> str:
    normalized = re.sub(r"(?<!\w)([^\W\d_]{1,3})\.(?=\s)", r"\1", name_key(text))
    return "".join(c for c in unicodedata.normalize("NFD", normalized) if not unicodedata.combining(c))


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


def matching_names(raw, hits, *, contextual_query=""):
    exact, close, partial = {}, {}, {}
    typed_words = name_key(raw).split()
    possessive = re.compile(r"(?<=\w)'s\b")
    typed_without_possessives = possessive.sub("", spelling_key(raw))
    typed_compact = typed_without_possessives.replace(" ", "")
    typed_tokens = sorted(typed_without_possessives.split())
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
        # A comma can delimit a character's epithet in the source title.
        lead, separator, _ = title.partition(",")
        if separator and close_spelling(raw, lead):
            names.append(lead)
        bucket = exact if any(name_key(raw) == name_key(s) for s in names) else close
        if bucket is exact or any(
            close_spelling(raw, s)
            or typed_without_possessives == possessive.sub("", spelling_key(s))
            or (len(typed_tokens) >= 3 and sorted(possessive.sub("", spelling_key(s)).split()) == typed_tokens)
            or (
                len(typed_words) == 2
                and len(typed_compact) >= 8
                and spelling_key(s).isalpha()
                and close_spelling(typed_compact, s)
            )
            for s in names
        ):
            bucket.setdefault(name_key(title), (title, []))[1].append(hit)
        elif (
            contextual_query
            and name_key(title).startswith(name_key(raw) + " ")
            and contains_name(contextual_query, title)
        ):
            # A more specific search may recover the full title of a shortened name.
            close.setdefault(name_key(title), (title, []))[1].append(hit)
        elif (
            contextual_query
            and len(typed_words) == 1
            and len(typed_words[0]) >= 5
            and any(
                word.isalpha()
                and spelling_key(word) != spelling_key(raw)
                and close_spelling(raw, word)
                and (contains_name(contextual_query, raw) or contains_name(contextual_query, word))
                for name in names
                for word in (name.split()[:1] + name.split()[-1:])
            )
        ):
            close.setdefault(name_key(title), (title, []))[1].append(hit)
        elif len(typed_words) >= 2 and all(word in name_key(title).split() for word in typed_words):
            partial.setdefault(name_key(title), (title, []))[1].append(hit)
    # A partial title provides options for clarification, never grounds an automatic correction.
    return list((exact or close or partial).values()), bool(exact or close)


def correct_name(text: str, raw: str, canonical: str) -> str:
    names = [r"(?:\s*,\s*|\s+)".join(map(re.escape, re.split(r"[\s,]+", name.strip()))) for name in (canonical, raw)]
    pattern = r"(?<!\w)(?:" + "|".join(names) + r")(?!\w)"
    return re.sub(pattern, lambda _: canonical, text, flags=re.I)
