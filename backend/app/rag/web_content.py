"""Conservative Markdown cleaning and query-aware selection. No new gameplay facts."""

import re
from urllib.parse import unquote

from app.rag.overview import folded

IMAGE = re.compile(r"!\[[^\]\n]*\]\([^\n]*?\)")
LINK = re.compile(r"\[([^\]\n]*)\]\([^\s)]+(?:\s+\"[^\"]*\")?\)")
REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*https?://.*$", re.M)
NOISE = re.compile(
    r"^(?:sign in(?: now)?|log in|navigation|main page|recent changes|random page|"
    r"help about mediawiki|visit the main page|advertisement|cookie settings|"
    r"privacy policy|terms of service|follow us|share this article)\s*$",
    re.I,
)


def clean_markdown(raw: str) -> tuple[str, dict]:
    stats = {"image_markup_removed": 0, "link_markup_removed": 0, "navigation_lines_removed": 0}
    # Tavily returns Markdown, not the display-escaped copy sometimes pasted from a UI.
    # Do not unescape arbitrary gameplay text or parse JSON inside source content.
    text, stats["image_markup_removed"] = IMAGE.subn("", raw)
    text, stats["link_markup_removed"] = LINK.subn(lambda match: match[1], text)
    text = REFERENCE.sub("", text)
    inline_heading = re.search(r"(?<!\S)#\s+\S", text)
    if inline_heading is not None and re.search(
        r"navigation|sign in|recent changes|fextralife|mediawiki", text[: inline_heading.start()], re.I
    ):
        stats["navigation_lines_removed"] += len(text[: inline_heading.start()].splitlines())
        text = text[inline_heading.start() :]
    lines = text.splitlines()
    # Known wiki skin navigation before the first article H1, with a clear marker.
    first_heading = next((i for i, line in enumerate(lines) if re.match(r"^#\s+\S", line)), None)
    if first_heading is not None and any(
        re.search(r"navigation|sign in|recent changes|fextralife|mediawiki", line, re.I)
        for line in lines[:first_heading]
    ):
        stats["navigation_lines_removed"] += first_heading
        lines = lines[first_heading:]
    kept = []
    for line in lines:
        visible = re.sub(r"^[\s*\-#>]+", "", line).strip()
        if NOISE.fullmatch(visible):
            stats["navigation_lines_removed"] += 1
            continue
        if visible or (kept and kept[-1]):
            kept.append(line.rstrip())
    return "\n".join(kept).strip(), stats


def select_excerpts(text: str, query: str, *, limit: int = 3) -> tuple[list[str], int]:
    """Rank whole blocks by lexical coverage; retain headings/table headers, no similarity claims."""
    tokens = set(re.findall(r"[a-z0-9]+", folded(query))) - {
        "elden",
        "ring",
        "search",
        "focus",
        "the",
        "a",
        "of",
        "in",
        "is",
        "what",
        "how",
        "to",
        "and",
    }
    candidates, heading, excluded, current = [], "", 0, ""
    for ordinal, raw in enumerate(re.split(r"\n\s*\n", text)):
        lines = raw.splitlines()
        # Keep section context attached to content blocks, without copying unrelated navigation.
        headings = [line for line in lines if re.match(r"^#{1,6}\s+\S", line)]
        if headings:
            heading = headings[-1]
        block = raw.strip()
        if heading and heading not in block:
            block = heading + "\n\n" + block
        if not block or len(block) < 8:
            continue
        if len(block) > 3500:
            excluded += 1
            continue  # Do not silently cut a table or a gameplay condition.
        # Pack in source order before ranking so quest steps are never reordered inside an excerpt.
        if current and len(current) + len(block) + 2 > 3500:
            words = set(re.findall(r"[a-z0-9]+", folded(unquote(current))))
            candidates.append((len(tokens & words), ordinal, current))
            current = ""
        current = (current + "\n\n" + block).strip()
    if current:
        words = set(re.findall(r"[a-z0-9]+", folded(unquote(current))))
        candidates.append((len(tokens & words), len(candidates) + len(text), current))
    ranked = sorted(candidates, key=lambda row: (-row[0], row[1]))
    selected, seen = [], set()
    for _, _, block in ranked:
        if block in seen:
            continue
        seen.add(block)
        selected.append(block)
        if len(selected) == limit:
            break
    return selected, excluded
