"""S1 source comparisons and small API probes; never builds the TV3 entity table."""

from urllib.parse import quote

from bs4 import BeautifulSoup

from ingest.artifacts import now, save
from ingest.crawl.http import CrawlError, HttpClient
from ingest.settings import load_settings

TITLES = [
    "Ranni the Witch",
    "Melina",
    "Millicent",
    "Fia",
    "Sorcerer Rogier",
    "Nepheli Loux",
    "Miriel, Pastor of Vows",
    "Starscourge Radahn",
    "Golden Order",
    "Fingerslayer Blade",
]


def outline(html):
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".mw-parser-output, #page-content")
    if body is None:
        raise CrawlError("No article body; possible challenge")
    for tag in body.select("script,style,.navbox,.toc,.mw-editsection"):
        tag.decompose()
    return {
        "characters": len(body.get_text(" ", strip=True)),
        "headings": [x.get_text(" ", strip=True) for x in body.find_all(["h2", "h3", "h4"])],
        "images": len(body.find_all("img")),
    }


def main():
    config = load_settings()
    client = HttpClient(config)
    report = {"checked_at": now(), "comparisons": [], "fanapis": [], "dump_checks": []}
    path = config["data_dir"] / "reports" / "source-survey.json"
    try:
        for title in TITLES:
            item = {"title": title}
            for name, base in [
                ("wikigg", "https://eldenring.wiki.gg/wiki/"),
                ("fandom", "https://eldenring.fandom.com/wiki/"),
            ]:
                url = base + quote(title.replace(" ", "_"), safe="")
                try:
                    response = client.get(url)
                    item[name] = {"url": url, "status": "ok", **outline(response.text)}
                    save(
                        config["data_dir"] / "research" / name / (quote(title, safe="") + ".json"),
                        {"url": url, "fetched_at": now(), "content": response.text},
                    )
                except CrawlError as exc:
                    item[name] = {"url": url, "status": "failed", "error": str(exc)}
            if all(item[n]["status"] == "ok" for n in ("wikigg", "fandom")):
                a, b = set(item["wikigg"]["headings"]), set(item["fandom"]["headings"])
                item["heading_overlap"] = len(a & b) / len(a | b) if a | b else 1
            report["comparisons"].append(item)
            save(path, report)
            print("COMPARE", title, flush=True)
        for resource in config["sources"]["fanapis"]["resources"]:
            row = {"resource": resource, "pages": []}
            for page in (0, 1):
                url = f"https://eldenring.fanapis.com/api/{resource}?limit=2&page={page}"
                try:
                    result = client.json(url)
                    row["pages"].append({"page": page, "status": "ok", "response": result})
                except CrawlError as exc:
                    row["pages"].append({"page": page, "status": "failed", "error": str(exc)})
            report["fanapis"].append(row)
            save(path, report)
        for url in [
            "https://eldenring.wiki.gg/wiki/Special:Statistics",
            "https://eldenring.wiki.gg/wiki/Special:Version",
        ]:
            try:
                response = client.get(url)
                soup = BeautifulSoup(response.text, "html.parser")
                links = [
                    {"url": x.get("href"), "label": x.get_text(" ", strip=True)}
                    for x in soup.find_all("a", href=True)
                    if any(t in (x["href"] + " " + x.get_text()).lower() for t in ("dump", "copyright", "license"))
                ]
                report["dump_checks"].append(
                    {
                        "url": url,
                        "status": "ok",
                        "links": links,
                        "conclusion": "no dump found on checked page"
                        if not any("dump" in str(x).lower() for x in links)
                        else "inspect links",
                    }
                )
            except CrawlError as exc:
                report["dump_checks"].append({"url": url, "status": "failed", "error": str(exc)})
            save(path, report)
    finally:
        report["finished_at"] = now()
        report["http"] = dict(client.stats)
        save(path, report)
        client.close()


if __name__ == "__main__":
    main()
