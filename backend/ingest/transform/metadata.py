"""Metadata inferred conservatively from source structure, without model calls."""

import re


def section_metadata(section, raw, html_lang):
    kinds = {b["kind"] for b in section["blocks"]}
    if kinds == {"dialogue"}:
        source_type = "in_game_text"
    elif re.search(r"\b(?:speculat\w*|theori[sz]\w*|possibly|perhaps|unclear)\b", section["text"], re.I):
        source_type = "speculation"
    elif section["section"].split(" > ")[-1].lower() in {"description", "descriptions"}:
        source_type = "unknown"
    elif kinds == {"prose"}:
        source_type = "wiki_prose"
    else:
        source_type = "unknown"
    if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", section["text"]):
        lang = "unknown"
    else:
        lang = "en" if html_lang == "en" else "unknown"
    return {"source_type": source_type, "lang": lang}
