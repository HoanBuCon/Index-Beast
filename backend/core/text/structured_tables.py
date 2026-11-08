"""Source-bound table grid and facts. Pure parsing: no files, network or model."""

import hashlib
import re
from collections import Counter

from core.text.lore_policy import tab_language
from core.text.table_quality import review_reason

VERSION = "s3-tables-1.0"
UI = {"navbox", "toc", "ambox", "metadata", "mw-cite-backlink"}
IDENTITY = re.compile(
    r"^(?:level|name|item(?: name)?|material name|location|condition|trigger|move name|patch|attribute)$", re.I
)
PLACEHOLDER = re.compile(r"^(?:\?+|TBA|TBD|Unknown|Please add a quote\.)$", re.I)


def stable(*parts):
    return hashlib.sha256("\0".join(map(str, parts)).encode()).hexdigest()


def row_metadata(row_key):
    match = re.search(r"(?:^|;\s*)Level:\s*([^;]+)", row_key or "", re.I)
    level = match[1].strip() if match else None
    return {
        "level": level,
        "row_kind": "growth_rate" if level and re.search(r"/Lv|per level", level, re.I) else "source_row",
    }


def plain(node):
    return " ".join(node.get_text(" ", strip=True).split())


def grid(table):
    """Return expanded references to original cells; never guess a missing cell."""
    rows = [r for r in table.find_all("tr") if r.find_parent("table") is table]
    if len(rows) > 4096:
        return [], [], ["row_limit"]
    occupied, cells, issues = {}, [], []
    for ri, row in enumerate(rows):
        ci = 0
        for source_ci, cell in enumerate(row.find_all(["td", "th"], recursive=False)):
            while (ri, ci) in occupied:
                ci += 1
            try:
                rs, cs = int(cell.get("rowspan", 1)), int(cell.get("colspan", 1))
                if rs == 0:
                    group = row.find_parent(["thead", "tbody", "tfoot"])
                    rs = sum(r.find_parent(["thead", "tbody", "tfoot"]) is group for r in rows[ri:])
                if rs < 1 or cs < 1 or cs > 128 or ri + rs > len(rows) or ci + cs > 128:
                    raise ValueError
            except (ValueError, TypeError):
                issues.append(f"invalid_span:r{ri}c{source_ci}")
                rs, cs = 1, 1
            record = {
                "cell_id": f"r{ri}c{source_ci}",
                "row": ri,
                "column": ci,
                "rowspan": rs,
                "colspan": cs,
                "tag": cell.name,
                "text": plain(cell),
                "labels": [x.get("alt") or x.get("title") for x in cell.select("img[alt],img[title],abbr[title]")],
                "styles": sorted({x.get("style") for x in [cell, *cell.find_all(style=True)] if x.get("style")}),
            }
            cells.append(record)
            for rr in range(ri, ri + rs):
                for cc in range(ci, ci + cs):
                    if (rr, cc) in occupied:
                        issues.append(f"overlapping_span:r{rr}c{cc}")
                    else:
                        occupied[rr, cc] = record
            ci += cs
    width = max((c for _, c in occupied), default=-1) + 1
    return [[occupied.get((r, c)) for c in range(width)] for r in range(len(rows))], cells, issues


def category(section, header, infobox, ui, cells):
    if ui:
        return "ui_or_outside_article"
    if re.search(r"(?:^| > )References?\b", section, re.I):
        return "references_or_citations"
    if re.search(r"\bLevel\b", header, re.I) and re.search(r"Scaling|\bAtk\b|Grd Boost", header, re.I):
        return "upgrade_stats"
    if infobox:
        return "infobox_table"
    if re.search(r"Dialogue", section + " " + header, re.I):
        return "dialogue_table"
    for pattern, kind in [
        (r"^Patch.*Official notes", "patch_history"),
        (r"Material name", "crafting_recipe"),
        (r"Drop rate", "drop_rates"),
        (r"Item name.*Runes|Required remembrance", "shop_or_exchange"),
        (r"Right hand.*Left hand|Move Name", "combat_loadout_or_moves"),
        (r"Ash of War.*Affinity|All affinities", "affinity_compatibility"),
        (r"(?:Icon|Image).*(?:Name|Item|Effect|Location|Requirements)", "item_catalog"),
        (r"Damage|Attack|Scaling|Resistan|\bHP\b|\bFP\b|Poise|Defense|Negation", "other_stats_or_combat"),
    ]:
        if re.search(pattern, header, re.I):
            return kind
    if any(c["text"] in {"“", "”"} for c in cells):
        return "quote_layout"
    return "other_unclassified"


def extract(soup, title, positions):
    """Inventory every raw table. Parsed row blocks only contain source-labelled facts."""
    body = soup.select_one(".mw-parser-output, #page-content, main")
    sections, path = {}, []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "table"]):
        if node.name == "table":
            sections[id(node)] = " > ".join(t for _, t in path) or "Introduction"
        elif not any("portable-infobox" in a.get("class", []) for a in node.parents if hasattr(a, "get")):
            level = int(node.name[1])
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, plain(node).replace("[ edit ]", "").strip()))
    result = {}
    for ordinal, table in enumerate(soup.find_all("table")):
        ancestors = [table, *table.parents]
        in_body = body is not None and any(a is body for a in ancestors)
        ui = not in_body or any(
            getattr(a, "name", None) in {"nav", "footer", "header"} or UI & set(a.get("class", []))
            for a in ancestors
            if hasattr(a, "get")
        )
        infobox = any("portable-infobox" in a.get("class", []) for a in ancestors if hasattr(a, "get"))
        expanded, cells, issues = grid(table)
        header_count = 0
        for row in expanded:
            present = [c for c in row if c]
            if present and all(c["tag"] == "th" for c in present):
                header_count += 1
            else:
                break
        # Some source templates use td for a header. Require explicit field names.
        if (
            not header_count
            and expanded
            and sum(
                bool(
                    re.fullmatch(
                        r"Level|Atk|Name|Item|Item Name|Effect|Location|Requirements|Dialogue|Condition",
                        c["text"],
                        re.I,
                    )
                )
                for c in expanded[0]
                if c
            )
            >= 2
        ):
            header_count = 1
        headers = []
        width = len(expanded[0]) if expanded else 0
        for col in range(width):
            values = []
            for row in expanded[:header_count]:
                c = row[col]
                if c:
                    label = c["text"] or " ".join(filter(None, c["labels"]))
                    if not c["text"]:
                        label = re.sub(r"^ER (?:Custom Stat|Menu) Icon\s+", "", label)
                        label = re.sub(r"\.png$", "", label, flags=re.I)
                    if label and label not in values:
                        values.append(label)
            headers.append(" / ".join(values))
        # Same '#' label has different roles next to Item name / Material name.
        for col, label in enumerate(headers):
            if label == "#" and col and re.fullmatch(r"Item name|Material name", headers[col - 1], re.I):
                headers[col] = headers[col - 1] + " / #"
        header = " | ".join(headers)
        section = "Infobox" if infobox else sections[id(table)]
        kind = category(section, header, infobox, ui, cells)
        variant = None
        for parent in ancestors:
            if hasattr(parent, "get") and {"tabber__panel", "tabbertab"} & set(parent.get("class", [])):
                variant = parent.get("data-title") or parent.get("title") or parent.get("id")
                break
        lang = tab_language(variant) or "unknown"
        outside = bool(
            re.search(r"Nightreign|Tarnished Edition|Cut content|Unused|Behind the scenes", title + " " + section, re.I)
        )
        table_id = f"table:{ordinal}"
        inventory = {
            "table_id": table_id,
            "table_index": ordinal,
            "location": positions.get(id(table), f"outside_article:table:{ordinal}"),
            "section": section,
            "table_type": kind,
            "variant": variant,
            "headers": headers,
            "header_rows": header_count,
            "cells": cells,
            "grid_issues": issues,
            "facts": [],
            "blocks": [],
        }
        if ui or kind == "references_or_citations":
            inventory.update(decision="excluded", reason="interface_or_reference_layout")
            for c in cells:
                c.update(decision="excluded", reason=inventory["reason"])
            result[id(table)] = inventory
            continue
        if issues or table.find("table") or outside:
            reason = (
                "grid_conflict"
                if issues
                else "nested_table_container"
                if table.find("table")
                else "outside_or_editorial_scope"
            )
            inventory.update(decision="review", reason=reason)
            for c in cells:
                c.update(decision="review", reason=reason)
            result[id(table)] = inventory
            continue
        for c in cells:
            c.update(decision="review", reason="unresolved_cell_role")
            if c["row"] < header_count:
                c.update(decision="keep", reason="source_header")
        if kind == "dialogue_table" and width == 1:
            inventory.update(decision="keep", reason="existing_typed_dialogue_parser", renderer="legacy_dialogue")
            for c in cells:
                c.update(decision="keep", reason="existing_typed_dialogue_parser")
            result[id(table)] = inventory
            continue
        if kind == "quote_layout":
            content = [c for c in cells if c["text"] and c["text"] not in {"“", "”"}]
            if len(content) == 1 and not PLACEHOLDER.fullmatch(content[0]["text"]):
                inventory["blocks"].append({"text": content[0]["text"], "fact_ids": [], "row_key": "source_quote"})
                for c in cells:
                    c.update(decision="keep", reason="source_quote_layout")
                inventory.update(decision="keep", reason="source_quote_layout", cell_decisions={"keep": len(cells)})
                result[id(table)] = inventory
                continue
        seen = set()
        for ri, row in enumerate(expanded[header_count:], header_count):
            context = []
            for col, c in enumerate(row):
                leaf = headers[col].split(" / ")[-1] if col < len(headers) else ""
                if c and IDENTITY.fullmatch(leaf) and headers.count(headers[col]) == 1:
                    context.append(leaf + ": " + c["text"].rstrip(":"))
            row_key = "; ".join(dict.fromkeys(context))
            values, fact_ids = [], []
            row_facts = []
            # Repeated Level with several Atk source cells needs a source subtype legend.
            for col, c in enumerate(row):
                if c is None or c["colspan"] > 1:
                    continue
                label = headers[col] if col < len(headers) else ""
                value_cell = c
                # Label/value pairs under grouped infobox headers.
                paired = (
                    c["text"].endswith(":")
                    and col + 1 < len(row)
                    and row[col + 1]
                    and row[col + 1]["tag"] == "td"
                    and headers[col] == headers[col + 1]
                )
                if paired:
                    value_cell = row[col + 1]
                    label = " / ".join(filter(None, [label, c["text"].rstrip(":")]))
                    c.update(decision="keep", reason="source_field_label")
                elif col and row[col - 1] and row[col - 1]["text"].endswith(":") and headers[col - 1] == headers[col]:
                    continue
                key = (value_cell["cell_id"], label, row_key)
                if key in seen:
                    continue
                seen.add(key)
                value = value_cell["text"]
                reason = None
                if not value or label.lower() in {"icon", "image"}:
                    value_cell.update(decision="excluded", reason="decorative_or_empty_cell")
                    continue
                if not label or not header_count or not row_key and kind not in {"infobox_table", "dialogue_table"}:
                    reason = "missing_header_or_row_identity"
                if kind == "infobox_table" and not paired and not row_key:
                    reason = "missing_attribute_or_field_identity"
                if PLACEHOLDER.fullmatch(value):
                    reason = "source_placeholder"
                if headers.count(label) > 1 and not paired:
                    reason = "ambiguous_repeated_header"
                if re.search(r"Nightreign|Tarnished Edition", label + " " + value + " " + row_key, re.I):
                    reason = "outside_base_sote_context"
                if re.fullmatch(r"Atk|Attack Power", label, re.I) and context:
                    level_col = next((i for i, h in enumerate(headers) if h.lower() == "level"), None)
                    same_level = [
                        rr[col]
                        for rr in expanded[header_count:]
                        if level_col is not None
                        and rr[level_col]
                        and row[level_col]
                        and rr[level_col]["text"] == row[level_col]["text"]
                        and rr[col]
                    ]
                    if len({x["cell_id"] for x in same_level}) > 1:
                        reason = "ambiguous_attack_subtype"
                if kind in {"other_unclassified", "affinity_compatibility"} and not header_count:
                    reason = "unclassified_table_schema"
                reason = reason or review_reason(value, row_key)
                decision = "review" if reason else "keep"
                value_cell.update(decision=decision, reason=reason or "source_labelled_value")
                grade = re.fullmatch(r"([A-S])\s+(\d*\.\d+)", value)
                fact_lang = (
                    "ja"
                    if re.search(r"Japanese|日本語", label, re.I)
                    else "en"
                    if re.search(r"English", label, re.I)
                    else lang
                )
                if fact_lang == "unknown" and not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", value):
                    fact_lang = body.get("lang", "unknown") if body else "unknown"
                if fact_lang == "en" and re.search(r"[\u3040-\u30ff\u3400-\u9fff]", value):
                    fact_lang = "unknown"
                record = {
                    "fact_id": f"{table_id}:{value_cell['cell_id']}:{stable(label, row_key)[:12]}",
                    "table_id": table_id,
                    "row_index": ri,
                    "row_key": row_key,
                    "column_index": value_cell["column"],
                    "cell_id": value_cell["cell_id"],
                    "stat_name": label,
                    "raw_cell_text": value,
                    "value": value,
                    "scaling_grade": grade[1] if grade else None,
                    "coefficient": grade[2] if grade else None,
                    "damage_type": None,
                    "unit": "%" if re.fullmatch(r"[+-]?\d+(?:\.\d+)?%", value) else None,
                    "decision": decision,
                    "reason": reason or "source_labelled_value",
                    "lang": fact_lang,
                }
                inventory["facts"].append(record)
                row_facts.append(record)
                if decision == "keep":
                    values.append(f"{label}: {grade[1] + '; coefficient: ' + grade[2] if grade else value}")
                    fact_ids.append(record["fact_id"])
            if values:
                if kind == "dialogue_table":
                    context_facts = [
                        f
                        for f in row_facts
                        if f["decision"] == "keep" and not re.search("dialogue", f["stat_name"], re.I)
                    ]
                    speech = [
                        f for f in row_facts if f["decision"] == "keep" and re.search("dialogue", f["stat_name"], re.I)
                    ]
                    for language in dict.fromkeys(f["lang"] for f in speech):
                        group = context_facts + [f for f in speech if f["lang"] == language]
                        inventory["blocks"].append(
                            {
                                "text": "\n".join(f["stat_name"] + ": " + f["value"] for f in group),
                                "fact_ids": [f["fact_id"] for f in group],
                                "row_key": row_key,
                                "lang": language,
                            }
                        )
                else:
                    inventory["blocks"].append(
                        {
                            "text": "\n".join(dict.fromkeys(values)),
                            "fact_ids": fact_ids,
                            "row_key": row_key,
                            "lang": lang,
                        }
                    )
        decisions = Counter(c["decision"] for c in cells)
        inventory.update(
            decision="keep" if inventory["blocks"] else "review",
            reason="partially_resolved_table"
            if inventory["blocks"] and decisions["review"]
            else "source_labelled_rows"
            if inventory["blocks"]
            else "unresolved_table_schema",
            cell_decisions=dict(decisions),
        )
        result[id(table)] = inventory
    return result
