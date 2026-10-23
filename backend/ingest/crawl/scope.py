"""Conservative S1 sample eligibility, not full section-level scope classification."""

import re

from bs4 import BeautifulSoup

DLC = re.compile(
    r"Shadow.of.the.Erdtree|Nightreign|Tarnished.Edition|Realm.of.Shadow|Gravesite.Plain|Scadu.Altus|Scadutree|Jagged.Peak|Cerulean.Coast|Rauh.Ruins|Enir.Ilim",
    re.I,
)


def sample_scope_reason(raw):
    soup = BeautifulSoup(raw["content"], "html.parser")
    body = soup.select_one(".mw-parser-output, #page-content, main") or soup
    # Infobox location/region is useful evidence even when category is only "Locations".
    infobox = " ".join(tag.get_text(" ", strip=True) for tag in body.select(".portable-infobox"))
    for node in body.select(".navbox,.toc,.portable-infobox,script,style"):
        if node.parent:
            node.decompose()
    lead = body.get_text(" ", strip=True)[:1000]
    match = DLC.search(raw["title"] + " " + infobox + " " + lead)
    return "out_of_scope_or_mixed_lead:" + match.group(0) if match else None
