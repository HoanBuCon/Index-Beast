"""Pure token-budget chunking. The caller supplies a local tokenizer; no network/encoder."""

import re


def token_count(tokenizer, text):
    return len(tokenizer.encode(text, add_special_tokens=True).ids)


def context_prefix(doc, section, unit):
    lines = [f"passage: {doc['title']}", section["section"]]
    variant = section.get("variant_context")
    if variant and variant.get("label"):
        lines.append("Variant: " + variant["label"])
    if unit.get("lang") not in (None, "unknown"):
        lines.append("Language: " + unit["lang"])
    if unit.get("speaker"):
        lines.append("Speaker: " + unit["speaker"])
    if unit.get("trigger"):
        lines.append("Trigger: " + unit["trigger"])
    if unit.get("table_header"):
        lines.append("Table header: " + unit["table_header"])
    return "\n".join(lines) + "\n"


def split_unit(text, prefix, tokenizer, cap=450, overlap=50):
    """Exact source character slices; repeat context and re-encode every final string."""
    if token_count(tokenizer, prefix) >= cap:
        raise ValueError("context_prefix_over_budget")
    spans = []
    start = 0
    while start < len(text):
        if token_count(tokenizer, prefix + text[start:]) <= cap:
            end = len(text)
        else:
            lo, hi = start + 1, len(text)
            end = start
            while lo <= hi:
                mid = (lo + hi) // 2
                if token_count(tokenizer, prefix + text[start:mid]) <= cap:
                    end = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            if end == start:
                raise ValueError("context_leaves_no_text_budget")
            # Prefer paragraph/sentence boundaries without creating tiny fragments.
            matches = list(re.finditer(r"\n|[.!?。！？](?:\s|$)", text[start:end]))
            boundaries = [start + m.end() for m in matches if m.end() >= (end - start) // 2]
            if boundaries:
                end = boundaries[-1]
        fragment = text[start:end]
        if token_count(tokenizer, prefix + fragment) > cap:
            raise AssertionError("Token cap exceeded")
        spans.append(
            {
                "start_char": start,
                "end_char": end,
                "text": fragment,
                "embedding_text": prefix + fragment,
                "token_count": token_count(tokenizer, prefix + fragment),
            }
        )
        if end == len(text):
            break
        lo, hi = 0, max(0, len(fragment) - 1)
        tail = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            suffix = fragment[len(fragment) - mid :] if mid else ""
            if len(tokenizer.encode(suffix, add_special_tokens=False).ids) <= overlap:
                tail = mid
                lo = mid + 1
            else:
                hi = mid - 1
        start = max(start + 1, end - tail)
    return spans


def prepare_units(doc, section, tokenizer, cap):
    units = []
    buffer = []
    indices = []

    def flush():
        nonlocal buffer, indices
        if buffer:
            units.append(
                {
                    "unit_key": f"blocks:{indices[0]}-{indices[-1]}",
                    "kind": buffer[0]["kind"],
                    "text": "\n".join(b["text"] for b in buffer),
                    "lang": section["lang"],
                    "trigger": None,
                    "speaker": None,
                    "block_indices": indices[:],
                    "source_locations": [b["location"] for b in buffer],
                }
            )
        buffer = []
        indices = []

    for index, block in enumerate(section["blocks"]):
        if block["kind"] == "dialogue":
            flush()
            if not block.get("turns"):
                raise ValueError("Dialogue lacks typed turns; run clean v2 first")
            for turn in block["turns"]:
                units.append(
                    dict(
                        turn,
                        unit_key=f"block:{index}/turn:{turn['unit_ordinal']}",
                        kind="dialogue",
                        block_indices=[index],
                        source_locations=[block["location"]],
                    )
                )
        elif block["kind"] == "table":
            flush()
            units.append(
                {
                    "unit_key": f"block:{index}",
                    "kind": "table",
                    "text": block["text"],
                    "table_header": block["text"].splitlines()[0],
                    "lang": section["lang"],
                    "trigger": None,
                    "speaker": None,
                    "block_indices": [index],
                    "source_locations": [block["location"]],
                }
            )
        else:
            candidate = "\n".join([b["text"] for b in buffer] + [block["text"]])
            prefix = context_prefix(doc, section, {"lang": section["lang"]})
            if buffer and token_count(tokenizer, prefix + candidate) > cap:
                flush()
            buffer.append(block)
            indices.append(index)
    flush()
    if "\n".join(u["text"] for u in units) != section["text"]:
        raise ValueError("Unit preparation changed section source text")
    return units


def chunk_section(doc, section, tokenizer, cap=450, overlap=50):
    if not 64 <= cap <= 500 or not 0 <= overlap < cap // 2:
        raise ValueError("Invalid token budget/overlap")
    chunks = []
    reviews = []
    coverage = []
    for unit in prepare_units(doc, section, tokenizer, cap):
        prefix = context_prefix(doc, section, unit)
        try:
            spans = split_unit(unit["text"], prefix, tokenizer, cap, overlap)
        except ValueError as exc:
            reviews.append(
                {
                    "unit_key": unit["unit_key"],
                    "reason": str(exc),
                    "text": unit["text"],
                    "trigger": unit.get("trigger"),
                    "speaker": unit.get("speaker"),
                }
            )
            coverage.append({"unit_key": unit["unit_key"], "status": "review", "source_chars": len(unit["text"])})
            continue
        end = 0
        for ordinal, span in enumerate(spans):
            if span["start_char"] > end or span["text"] != unit["text"][span["start_char"] : span["end_char"]]:
                raise ValueError("Gap or changed text in chunk coverage")
            end = max(end, span["end_char"])
            chunks.append(
                dict(
                    span,
                    unit_key=unit["unit_key"],
                    unit_kind=unit["kind"],
                    unit_ordinal=ordinal,
                    trigger=unit.get("trigger"),
                    speaker=unit.get("speaker"),
                    lang=unit.get("lang", "unknown"),
                    source_locations=unit["source_locations"],
                    source_text_hash_input=unit["text"],
                )
            )
        if end != len(unit["text"]):
            raise ValueError("Incomplete unit coverage")
        coverage.append(
            {
                "unit_key": unit["unit_key"],
                "status": "covered",
                "source_chars": len(unit["text"]),
                "chunks": len(spans),
                "trigger_repeated_in_context": bool(unit.get("trigger")),
            }
        )
    return {"chunks": chunks, "reviews": reviews, "coverage": coverage}
