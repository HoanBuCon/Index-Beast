"""Conservative Markdown cleaning and page-order block splitting. No new gameplay facts, no ranking."""

import re

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


def select_excerpts(text: str, *, limit: int = 6) -> tuple[list[str], int]:
    """Split a page into blocks in page order; no ranking (22/11: the Agent chooses which blocks to open).

    Blocks keep their section heading and are packed up to ~3,500 characters without reordering, so quest steps
    and tables stay intact. `limit` is a size budget per page (the first blocks of the page), not a relevance
    claim. Returns the blocks and how many oversized blocks were excluded rather than silently cut.
    """
    blocks, heading, excluded, current = [], "", 0, ""
    for raw in re.split(r"\n\s*\n", text):
        lines = raw.splitlines()
        # Keep section context attached to content blocks, without copying unrelated navigation.
        headings = [line for line in lines if re.match(r"^#{1,6}\s+\S", line)]
        if headings:
            heading = headings[-1]
        block = raw.strip()
        if not block or len(block) < 8:
            continue
        # A block that starts a new packed chunk carries its section heading; inside a chunk it is already there.
        headed = heading + "\n\n" + block if heading and heading not in block else block
        if len(headed) > 3500:
            excluded += 1
            continue  # Do not silently cut a table or a gameplay condition.
        if current and len(current) + len(block) + 2 > 3500:
            blocks.append(current)
            current = ""
        current = (current + "\n\n" + (block if current and heading in current else headed)).strip()
    if current:
        blocks.append(current)
    unique = list(dict.fromkeys(blocks))
    return unique[:limit], excluded
