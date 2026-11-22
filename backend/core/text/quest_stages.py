"""Recover source-authored progression stages from wiki list structure."""

import re

from bs4 import BeautifulSoup

QUEST_SECTION = re.compile(r"\b(?:questline|quest progression|walkthrough)\b", re.I)


def stage_locations(html):
    """A one-link bullet immediately preceding a numbered list labels its stage."""
    body = BeautifulSoup(html, "html.parser").select_one(".mw-parser-output, #page-content, main")
    if body is None:
        raise ValueError("Article body not found")
    stages = set()
    for index, tag in enumerate(body.find_all(True)):
        if tag.name != "li" or tag.parent.name != "ul" or len(tag.parent.find_all("li", recursive=False)) != 1:
            continue
        following = tag.parent.find_next_sibling()
        if following is None or following.name != "ol" or len(tag.find_all("a", href=True)) != 1:
            continue
        if tag.find(["ol", "ul", "table"]):
            continue
        stages.add(f"dom:{index}:li" + (f"#{tag['id']}" if tag.get("id") else ""))
    return stages
