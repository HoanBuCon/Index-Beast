"""Conservative scope decisions with evidence; unknown content stays in review."""

import re

from bs4 import BeautifulSoup


def pattern(words):
    if not words:
        return re.compile(r"(?!)")
    return re.compile("|".join(re.escape(w).replace(r"\ ", r"[ _]+") for w in words), re.I)


def page_evidence(raw, config):
    soup = BeautifulSoup(raw["content"], "html.parser")
    location = " ".join(
        n.get_text(" ", strip=True)
        for n in soup.select('.pi-data[data-source="location"], .pi-data[data-source="region"]')
    )
    body = soup.select_one(".mw-parser-output, #page-content, main") or soup
    for node in body.select("aside,.portable-infobox,.navbox,.toc,script,style"):
        if node.parent:
            node.decompose()
    paragraphs = body.find_all("p", recursive=False)
    lead = " ".join(n.get_text(" ", strip=True) for n in paragraphs[:2])
    probe = location + " " + lead
    dlc = pattern(config["dlc_markers"]).search(probe)
    base = pattern(config["base_places"]).search(probe)
    if re.search(r"\b(?:is|are)\b[^.]{0,160}\bin Shadow of the Erdtree\b", lead, re.I):
        return {"status": "excluded", "reason": "explicit_dlc_lead_definition", "quote": lead[:400]}
    if dlc:
        return {"status": "review", "reason": "mixed_or_dlc_page_context", "quote": dlc.group(0)}
    if base:
        return {"status": "base", "reason": "base_place_in_lead_or_infobox", "quote": base.group(0)}
    return {"status": "review", "reason": "no_positive_scope_evidence", "quote": ""}


def section_decision(section, page, config):
    if page["status"] == "excluded":
        return "excluded", page["reason"]
    if "\ufffd" in section["text"]:
        return "review", "encoding_replacement_character"
    name = section["section"]
    text = section["text"]
    heading_dlc = pattern(config["dlc_markers"]).search(name)
    if heading_dlc:
        return "excluded", "explicit_dlc_heading:" + heading_dlc.group(0)
    if re.search(r"(?:^| > )(?:Unused|Cut content|Cut dialogue)(?:$| > )", name, re.I):
        return "excluded", "unused_or_cut_section"
    if pattern(config["dlc_markers"]).search(text):
        return "review", "dlc_or_mixed_marker_in_content"
    if pattern(config.get("uncertain_entities", [])).search(name + " " + text):
        return "review", "entity_from_explicit_dlc_or_mixed_sample"
    if page["reason"] == "mixed_or_dlc_page_context":
        return "review", page["reason"]
    if any(b["notes"] for b in section["blocks"]) and not re.search(
        r"Quest Items|Acquisition|Dialogue|Description", name, re.I
    ):
        return "review", "unclassified_structure_retained"
    if page["status"] == "base":
        return "base", page["reason"] + ":" + page["quote"]
    local = pattern(config["base_places"]).search(text)
    if local and section["kind"] != "infobox":
        return "base", "base_place_in_section:" + local.group(0)
    return "review", page["reason"]


def filter_document(raw, config):
    """Pure filter analysis; decisions precede metadata transformation and CSV export."""
    from core.text.html_clean import clean_html

    cleaned = clean_html(raw["content"], title=raw["title"], skip_sections=config["skip_sections"])
    evidence = page_evidence(raw, config)
    for section in cleaned["sections"]:
        status, reason = section_decision(section, evidence, config)
        section.update(scope_status=status, scope_reason=reason)
    cleaned["page_scope_evidence"] = evidence
    cleaned["source_id"] = raw["source_id"]
    cleaned["revision_id"] = raw["revision_id"]
    cleaned["raw_content_hash"] = raw["content_hash"]
    return cleaned
