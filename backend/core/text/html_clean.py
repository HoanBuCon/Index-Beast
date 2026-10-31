"""Pure structural HTML cleaner; each removed node has a source locator and reason."""

import re
from collections import Counter

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from core.text.normalize import normalize_text, normalized_key

VERSION = "s2-clean-2.1"
UI_CLASSES = {
    "navbox",
    "toc",
    "mw-editsection",
    "mw-cite-backlink",
    "catlinks",
    "printfooter",
    "wikigg-showcase__unit",
    "wds-global-navigation",
}
UI_TAGS = {"script", "style", "nav", "footer", "header", "button", "form", "noscript", "svg"}
NON_LORE_FIELDS = {
    "voice",
    "voice_actor",
    "max_held",
    "max_stored",
    "trade",
    "runes",
    "hp",
    "fp",
    "weight",
    "sell",
    "buy",
    "cost",
}
STATS = re.compile(
    r"^(?:hp|fp|runes|damage negation|status resistances?|poise|defense|attack power|scaling|weight|"
    r"physical|magic|fire|lightning|holy)(?:\b|:)",
    re.I,
)


def render(node):
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return str(node)
    if node.name in UI_TAGS or set(node.get("class", [])) & UI_CLASSES:
        return ""
    if node.name == "sup" and "reference" in node.get("class", []):
        return ""
    if node.name == "br":
        return "\n"
    inner = "".join(render(x) for x in node.children)
    if node.name == "div":
        return " " + inner + " "
    return ("\n" + inner + "\n") if node.name in {"p", "li", "dt", "dd", "blockquote"} else inner


def clean_html(html: str, *, title: str, skip_sections=(), capture_context=False) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".mw-parser-output, #page-content, main")
    if body is None:
        raise ValueError("Article body not found")
    positions = {
        id(tag): f"dom:{n}:{tag.name}" + (f"#{tag['id']}" if tag.get("id") else "")
        for n, tag in enumerate(body.find_all(True))
    }
    anchor_counts = Counter(t.get("id") for t in body.find_all(id=True))

    def variant_context(node):
        if node is None:
            return None
        for parent in [node, *node.parents]:
            if not isinstance(parent, Tag):
                continue
            if set(parent.get("class", [])) & {"tabber__panel", "tabbertab"}:
                label = parent.get("data-title") or parent.get("title")
                if not label and parent.get("aria-labelledby"):
                    target = soup.find(id=parent["aria-labelledby"])
                    label = target.get_text(" ", strip=True) if target else None
                return {"label": label, "anchor": parent.get("id"), "source": "source_tab_label"}
        return None

    sections = []
    removed = []
    audited = set()
    heads = []
    active = None

    def new_section(path, locator, anchor="", kind="article", node=None):
        nonlocal active
        active = {"section": path, "location": locator, "anchor": anchor, "kind": kind, "blocks": []}
        variant = variant_context(node)
        active.update(variant_context=variant, heading_anchor=anchor)
        if anchor and anchor_counts[anchor] > 1 and variant and variant.get("anchor"):
            active["anchor"] = variant["anchor"]
            active["anchor_targets_variant_panel"] = True
        sections.append(active)

    new_section("Introduction", "article:start")

    def audit(node, reason, section=None, text=None):
        key = (id(node), reason)
        if key in audited:
            return
        audited.add(key)
        text = text or normalize_text(render(node))
        if not text:
            text = normalize_text(node.get_text(" ", strip=True))
        removed.append(
            {
                "section": section or active["section"],
                "location": positions.get(id(node), "article"),
                "reason": reason,
                "text": text,
            }
        )

    def add(node, text, kind="prose", notes=None, scan_inline=True):
        if scan_inline and isinstance(node, Tag):
            for marker in node.select("sup.reference,.mw-editsection,.mw-cite-backlink"):
                audit(marker, "inline_reference_or_edit_marker")
        text = normalize_text(text)
        if text and text not in {"|", "“", "”"}:
            active["blocks"].append(
                {"text": text, "kind": kind, "location": positions.get(id(node), "article"), "notes": notes or []}
            )
            if capture_context:
                block = active["blocks"][-1]
                block["variant_context"] = variant_context(node)
                block["source_citations"] = (
                    [a.get("href") for a in node.select("sup.reference a[href]")] if isinstance(node, Tag) else []
                )
                block["literal_description"] = bool(
                    re.search(r"(?:^| > )(?:Variant )?Descriptions?$", active["section"], re.I)
                ) and any(
                    isinstance(p, Tag)
                    and (
                        p.name in {"i", "em", "blockquote"}
                        or "font-style:italic" in p.get("style", "").replace(" ", "")
                    )
                    for p in [node, *node.parents]
                )

    def infobox(node):
        previous = active
        new_section("Infobox", positions.get(id(node), "article"), kind="infobox", node=node)
        # Theo thứ tự DOM: trường đơn (.pi-data) và nhóm "smart" (bảng/lưới chỉ số, không có class pi-data)
        items = node.select(".pi-data, .pi-smart-group")
        if not items:
            add(node, render(node), "infobox", ["unstructured_infobox_requires_review"])
        for item in items:
            if "pi-smart-group" in item.get("class", []):
                smart_group(node, item)
                continue
            key = (item.get("data-source") or item.get("data-item-name") or "").lower()
            label = item.select_one(".pi-data-label")
            value = item.select_one(".pi-data-value")
            if key in NON_LORE_FIELDS or (label and STATS.search(label.get_text(" ", strip=True))):
                audit(item, "infobox_numeric_or_production_field")
                continue
            if value:
                name = normalize_text(render(label)) if label else key
                add(item, f"{name}: {normalize_text(render(value))}", "infobox")
        return previous

    def smart_group(box, group):
        """Bảng hoặc lưới chỉ số (Attack Power, Attributes, Damage Negation…) thành dòng giữ nguyên giá trị nguồn."""
        header = group.find_previous(class_="pi-header")
        heading = [one_line(header)] if header and box in header.parents else []
        box_title = box.select_one(".pi-title")
        if box_title and one_line(box_title) != title:
            heading.insert(0, one_line(box_title))  # trang nhiều infobox (vd. hai phase của boss)
        table = group.find("table")
        labels = [one_line(x) for x in group.select(".pi-smart-data-label")]
        values = [one_line(x) for x in group.select(".pi-smart-data-value")]
        if table is not None:
            lines = infobox_table_lines(table)
        elif labels and len(labels) == len(values):
            lines = [", ".join(f"{label}: {value}" for label, value in zip(labels, values, strict=True))]
        else:
            audit(group, "infobox_unlabeled_value", text="\n".join(values))  # vd. tên tiếng Nhật không có nhãn
            return
        if not any(re.search(r"\d", line) for line in lines):
            audit(group, "infobox_placeholder_stats", text="\n".join(lines))  # khung bảng chưa có số liệu
            return
        if heading and lines and lines[0] == heading[-1]:
            lines = lines[1:]  # tiêu đề bảng trùng tiêu đề nhóm
        add(group, "\n".join([*heading, *lines]), "infobox_stats")

    def one_line(node):
        return " ".join(normalize_text(render(node)).split())

    def infobox_table_lines(table):
        """Dòng tiêu đề nhóm (th colspan) ghép với từng cặp nhãn/giá trị: 'Attack Power / Physical: 73'."""
        lines, groups = [], []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            texts = [one_line(c) for c in cells]
            if not any(texts):
                continue
            if all(c.name == "th" for c in cells):
                spans = [int(c.get("colspan") or 1) if str(c.get("colspan") or 1).isdigit() else 1 for c in cells]
                groups = list(zip(texts, spans, strict=True)) if len(cells) > 1 else []
                if len(cells) == 1 or all(span == 1 for span in spans):
                    lines.append(" | ".join(t for t in texts if t))
                continue
            if any(span > 1 for _, span in groups):
                column = 0
                for name, span in groups:
                    part = [t for t in texts[column : column + span] if t]
                    column += span
                    if len(part) > 1:
                        lines.append(f"{name} / {' '.join(part)}")
            else:
                lines.append(" | ".join(t for t in texts if t))
        return lines

    def table(node):
        rows = node.find_all("tr")
        text = normalize_text(render(node))
        labels = [
            normalize_text(cell.get_text(" ", strip=True))
            for cell in node.select("th, td")
            if len(cell.get_text(" ", strip=True)) < 100
        ]
        dialogue = "dialogue" in active["section"].lower() or any("dialogue" in label.lower() for label in labels)
        dialogue = dialogue or bool(re.search(r"(?:English|Japanese) Dialogue", text[:100], re.I))
        if not dialogue and sum(bool(STATS.search(v)) for v in labels) >= 2:
            audit(node, "numeric_stats_table")
            return
        if not dialogue and sum(v.casefold() in {"right hand", "left hand", "armor", "spells"} for v in labels) >= 2:
            audit(node, "combat_loadout_table")
            return
        # Layout tables with decorative quotation marks are kept as source quotations.
        quote = any(cell.get_text(strip=True) in {"“", "”"} for cell in node.select("td"))
        lines = []
        for row in rows:
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            values = [normalize_text(render(c)) for c in cells]
            values = [v for v in values if v and v not in {"|", "“", "”"}]
            if values:
                lines.append(" | ".join(values))
        notes = [] if dialogue or quote else ["table_retained_for_review"]
        add(node, "\n".join(lines), "dialogue" if dialogue else ("quote" if quote else "table"), notes)
        if dialogue and lines:
            # Preserve source row order and header roles; never infer the speaker from page title.
            units = []
            current = []
            trigger = None
            language = "unknown"
            has_speech = False

            def flush_turn():
                nonlocal current, has_speech
                if current:
                    units.append(
                        {
                            "unit_ordinal": len(units),
                            "text": "\n".join(current),
                            "trigger": trigger,
                            "speaker": node.get("data-speaker"),
                            "lang": language,
                            "source_location": positions.get(id(node), "article"),
                        }
                    )
                current = []
                has_speech = False

            for row in rows:
                cells = row.find_all(["td", "th"], recursive=False)
                values = [normalize_text(render(c)) for c in cells]
                values = [v for v in values if v and v not in {"|", "“", "”"}]
                if not values:
                    continue
                line = " | ".join(values)
                label = re.fullmatch(r"(English|Japanese) Dialogue", line, re.I)
                if label:
                    if has_speech:
                        flush_turn()
                    trigger = None
                    language = "en" if label.group(1).lower() == "english" else "ja"
                    current.append(line)
                    continue
                header = all(c.name == "th" for c in cells)
                if header:
                    if has_speech:
                        flush_turn()
                    trigger = line
                    current.append(line)
                else:
                    current.append(line)
                    has_speech = True
            flush_turn()
            if "\n".join(u["text"] for u in units) != "\n".join(lines):
                raise ValueError("Typed dialogue conversion changed source text")
            active["blocks"][-1]["turns"] = units

    def walk(node):
        nonlocal active, heads
        if isinstance(node, Comment):
            return
        if isinstance(node, NavigableString):
            value = normalize_text(str(node))
            if value:
                add(node.parent, value, scan_inline=False)
            return
        if not isinstance(node, Tag):
            return
        classes = set(node.get("class", []))
        if node.name in UI_TAGS or classes & UI_CLASSES:
            audit(node, "interface_or_navigation")
            return
        if node.name == "sup" and "reference" in classes:
            audit(node, "inline_reference_marker")
            return
        if node.name == "aside" or "portable-infobox" in classes:
            previous = infobox(node)
            active = previous
            return
        text = normalize_text(node.get_text(" ", strip=True))
        if text.casefold() in {"please add a quote.", "this section is empty."}:
            audit(node, "editorial_placeholder")
            return
        if len(text) < 500 and "This page is a stub" in text and "expanding it" in text:
            audit(node, "editorial_stub_notice")
            return
        if node.name == "div" and node.select_one("blockquote.quote"):
            quote = node.select_one("blockquote.quote")
            previous = node.find_previous_sibling()
            if (
                previous
                and "hidden" in previous.get("class", [])
                and normalized_key(render(quote)) == normalized_key(render(previous))
            ):
                audit(node, "duplicate_quote_display_variant")
                return
        if re.fullmatch(r"h[1-6]", node.name):
            level = int(node.name[1])
            heading = normalize_text(render(node))
            if level == 1 and heading == title:
                return
            heads = [(n, t) for n, t in heads if n < level]
            heads.append((level, heading))
            headline = node.select_one(".mw-headline[id]")
            anchor = node.get("id") or (headline.get("id") if headline else "")
            new_section(" > ".join(t for _, t in heads), positions.get(id(node), "article"), anchor, node=node)
            for marker in node.select(".mw-editsection"):
                audit(marker, "inline_reference_or_edit_marker")
            return
        if any(h.strip().casefold() in {v.casefold() for v in skip_sections} for _, h in heads):
            audit(node, "non_lore_section")
            return
        if node.name == "table":
            table(node)
            return
        if node.name in {"p", "li", "blockquote", "dt", "dd", "figcaption"}:
            add(node, render(node), "quote" if node.name == "blockquote" else "prose")
            return
        if node.name in {"img", "input", "meta", "link", "br", "hr"}:
            return
        for child in node.children:
            walk(child)

    if capture_context:
        for node in list(body.select('span[style*="float"]')):
            if "float:right" in node.get("style", "").replace(" ", "") and re.fullmatch(
                r"(?:Source:|\d+\.\d+(?:\.\d+)?)", node.get_text("", strip=True)
            ):
                heading = node.find_previous(["h2", "h3", "h4"])
                audit(
                    node,
                    "literal_description_version_label",
                    section=heading.get_text(" ", strip=True) if heading else "Introduction",
                )
                node.decompose()
    for child in body.children:
        walk(child)
    for n, section in enumerate(sections):
        section["ordinal"] = n
        section["text"] = "\n".join(b["text"] for b in section["blocks"])
    return {
        "sections": [s for s in sections if s["text"]],
        "removed": removed,
        "cleaning_version": VERSION,
        "html_lang": body.get("lang", "unknown"),
    }
