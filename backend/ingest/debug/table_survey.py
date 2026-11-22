"""Read-only raw HTML table census. Writes survey artifacts, never clean/chunk output."""

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from lxml import html


def text(node):
    return " ".join(" ".join(node.itertext()).split())


def span(cell, key):
    try:
        return int(cell.get(key, "1"))
    except ValueError:
        return -1


def survey(raw_root, output, delivery):
    if output.exists():
        raise ValueError("Use a new survey directory")
    output.mkdir(parents=True)
    totals, categories, flags = Counter(), Counter(), Counter()
    category_pages, flag_pages = defaultdict(set), defaultdict(set)
    shapes, examples, errors, fingerprints = Counter(), defaultdict(list), [], {}
    delivery_manifest_hash = hashlib.sha256(delivery.read_bytes()).hexdigest()
    with (output / "tables.jsonl").open("w", encoding="utf-8") as stream:
        for ordinal, path in enumerate(sorted(raw_root.rglob("*.json")), 1):
            payload = path.read_bytes()
            fingerprints[str(path.resolve())] = hashlib.sha256(payload).hexdigest()
            try:
                raw = json.loads(payload)
                assert hashlib.sha256(raw["content"].encode()).hexdigest() == raw["content_hash"]
                tree = html.fromstring(raw["content"])
                bodies = tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," mw-parser-output ")]')
                body = bodies[0] if bodies else None
                headings, section_map = [], {}
                for node in tree.iter():
                    if isinstance(node.tag, str) and re.fullmatch(r"h[1-6]", node.tag):
                        if any("portable-infobox" in a.get("class", "").split() for a in node.iterancestors()):
                            continue
                        depth = int(node.tag[1])
                        while headings and headings[-1][0] >= depth:
                            headings.pop()
                        headings.append((depth, text(node)))
                    if node.tag == "table":
                        section_map[node] = " > ".join(t for _, t in headings)
                page_tables = 0
                for index, table in enumerate(tree.iter("table")):
                    ancestors = list(table.iterancestors())
                    is_article = body is not None and (body is table or body in ancestors)
                    ui = any(
                        n.tag in {"nav", "footer", "header"}
                        or {"navbox", "toc", "metadata", "ambox"} & set(n.get("class", "").split())
                        for n in [table, *ancestors]
                    )
                    infobox = any("portable-infobox" in n.get("class", "").split() for n in ancestors)
                    rows = []
                    for row in table.iter("tr"):
                        if next(row.iterancestors("table"), None) is table:
                            rows.append([c for c in row if c.tag in {"th", "td"}])
                    values = [[text(c) for c in row] for row in rows]
                    header_cells = [text(c) for row in rows for c in row if c.tag == "th"]
                    header = " | ".join(header_cells[:40] or (values[0] if values else []))
                    section = "Infobox" if infobox else section_map[table]
                    cells = [c for row in rows for c in row]
                    merged = any(span(c, "rowspan") != 1 or span(c, "colspan") != 1 for c in cells)
                    style_colors = sorted(
                        {
                            v.strip()
                            for c in cells
                            for n in c.iter()
                            for v in re.findall(r"(?:^|;)\s*color\s*:\s*([^;]+)", n.get("style", ""), re.I)
                        }
                    )
                    table_flags = {
                        "rowspan": any(span(c, "rowspan") != 1 for c in cells),
                        "colspan": any(span(c, "colspan") != 1 for c in cells),
                        "invalid_or_zero_span": any(span(c, k) < 1 for c in cells for k in ["rowspan", "colspan"]),
                        "nested_table": any(n.tag == "table" for n in ancestors),
                        "contains_nested_table": bool(table.xpath(".//table")),
                        "inline_color": bool(style_colors),
                        "multiline_cell": any(c.xpath(".//br|.//p|.//div|.//li") for c in cells),
                        "grade_and_coefficient": any(re.fullmatch(r"[A-S]\s+\d*\.\d+", text(c)) for c in cells),
                        "multiple_numbers_in_cell": any(len(re.findall(r"\d+(?:\.\d+)?", text(c))) > 1 for c in cells),
                        "growth_rate_row": any(re.search(r"per level|/Lv", v, re.I) for row in values for v in row),
                        "cjk_text": any(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", v) for row in values for v in row),
                        "placeholder": any(
                            re.fullmatch(r"\?+|TBA|TBD|Unknown", v, re.I) for row in values for v in row
                        ),
                    }
                    upgrade = bool(
                        re.search(r"\bLevel\b", header, re.I) and re.search(r"Scaling|\bAtk\b|Grd Boost", header, re.I)
                    )
                    if not is_article or ui:
                        category = "ui_or_outside_article"
                    elif re.search(r"(?:^| > )References?\b", section, re.I):
                        category = "references_or_citations"
                    elif upgrade:
                        category = "upgrade_stats"
                    elif infobox:
                        category = "infobox_table"
                    elif re.search(r"Dialogue", header + " " + section, re.I):
                        category = "dialogue_table"
                    elif re.search(r"^Patch\s*\|.*Official notes", header, re.I):
                        category = "patch_history"
                    elif re.search(r"Material name", header, re.I):
                        category = "crafting_recipe"
                    elif re.search(r"Drop rate", header, re.I):
                        category = "drop_rates"
                    elif re.search(r"Item name.*Runes|Required remembrance", header, re.I):
                        category = "shop_or_exchange"
                    elif re.search(r"Right hand.*Left hand|Move Name", header, re.I):
                        category = "combat_loadout_or_moves"
                    elif re.search(r"Ash of War.*Affinity|All affinities", header, re.I):
                        category = "affinity_compatibility"
                    elif values and any(v in {"“", "”"} for v in values[0]):
                        category = "quote_layout"
                    elif not any(v for row in values for v in row):
                        category = "empty_or_media_layout"
                    elif re.search(r"\b(?:Icon|Image)\b", header, re.I) and re.search(
                        r"\b(?:Name|Item|Effect|Location|Requirements)\b", header, re.I
                    ):
                        category = "item_catalog"
                    elif re.search(
                        r"Damage|Attack|Scaling|Resistan|\bHP\b|\bFP\b|Poise|Defense|Negation", header, re.I
                    ):
                        category = "other_stats_or_combat"
                    else:
                        category = "other_unclassified"
                    active_flags = [k for k, v in table_flags.items() if v]
                    record = {
                        "source_id": str(raw["source_id"]),
                        "title": raw["title"],
                        "revision_id": raw["revision_id"],
                        "source_snapshot": str(path.resolve()),
                        "raw_content_hash": raw["content_hash"],
                        "url": raw["url"],
                        "table_index": index,
                        "xpath": table.getroottree().getpath(table),
                        "section": section,
                        "category": category,
                        "article": is_article,
                        "rows": len(rows),
                        "cells": len(cells),
                        "header": header,
                        "flags": active_flags,
                        "colors": style_colors,
                        "shape": [len(row) for row in rows[:12]],
                        "sample_cells": [
                            [
                                {"text": text(c)[:350], "rowspan": span(c, "rowspan"), "colspan": span(c, "colspan")}
                                for c in row[:8]
                            ]
                            for row in rows[:6]
                        ],
                    }
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                    categories[category] += 1
                    category_pages[category].add(record["source_id"])
                    totals["tables_all"] += 1
                    if category != "ui_or_outside_article":
                        page_tables += 1
                        totals["tables_article_non_ui"] += 1
                        totals["tables_article_merged"] += merged
                        totals["cells_article"] += len(cells)
                        for flag in active_flags:
                            flags[flag] += 1
                            flag_pages[flag].add(record["source_id"])
                        if category == "upgrade_stats":
                            shapes[header] += 1
                    if len(examples[category]) < 5:
                        examples[category].append(record)
                totals["pages_read"] += 1
                totals["pages_with_article_tables"] += page_tables > 0
                totals["pages_without_article_body"] += body is None
            except Exception as exc:
                errors.append({"path": str(path), "error": str(exc), "type": type(exc).__name__})
            if ordinal % 500 == 0:
                print(f"SURVEY {ordinal}", flush=True)
    assert hashlib.sha256(delivery.read_bytes()).hexdigest() == delivery_manifest_hash
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in fingerprints.items())
    result = {
        "totals": dict(totals),
        "categories": {k: {"tables": v, "pages": len(category_pages[k])} for k, v in categories.items()},
        "article_flags": {k: {"tables": v, "pages": len(flag_pages[k])} for k, v in flags.items()},
        "upgrade_header_families": dict(shapes),
        "examples": dict(examples),
        "errors": errors,
        "input_files_unchanged": True,
        "delivery_manifest_unchanged": True,
        "limitations": [
            "Heuristic structural census; categories are not semantic acceptance.",
            "Flags overlap; counts must not be added together.",
            "lxml used for survey only; production BeautifulSoup cleaner unchanged.",
        ],
        "network_calls": 0,
        "encoder_calls": 0,
        "database_writes": 0,
    }
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "input-fingerprints.json").write_text(json.dumps(fingerprints, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"examples", "upgrade_header_families"}}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args()
    survey(args.raw, args.output, args.delivery)
