"""MediaWiki discovery and revision-pinned HTML; no LLM calls."""

from urllib.parse import quote, urlencode

from ingest.artifacts import now, sha256
from ingest.crawl.http import CrawlError


class WikiGG:
    name = "wikigg"

    def __init__(self, client, config):
        self.client, self.config = client, config
        self.endpoint = config["sources"]["wikigg"]["api_url"]

    def api(self, **params):
        params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        for attempt in range(3):
            result = self.client.json(self.endpoint + "?" + urlencode(params))
            error = result.get("error")
            if not error:
                return result
            if error.get("code") != "maxlag" or attempt == 2:
                raise CrawlError("MediaWiki error: " + str(error.get("code", "unknown")))
            self.client.sleep(5 * (attempt + 1))
        raise CrawlError("maxlag retry exhausted")

    def list_category(self, category):
        members, continuation, seen = [], {}, set()
        while True:
            result = self.api(
                action="query",
                list="categorymembers",
                cmtitle="Category:" + category,
                cmprop="ids|title|type",
                cmlimit=500,
                **continuation,
            )
            if "categorymembers" not in result.get("query", {}):
                raise CrawlError("Missing categorymembers")
            members.extend(result["query"]["categorymembers"])
            continuation = result.get("continue", {})
            if not continuation:
                return list({x["pageid"]: x for x in members}.values())
            token = repr(sorted(continuation.items()))
            if token in seen:
                raise CrawlError("Repeated category continuation")
            seen.add(token)

    def describe(self, ids):
        pages = []
        for start in range(0, len(ids), 50):
            continuation, batch, seen = {}, {}, set()
            while True:
                result = self.api(
                    action="query",
                    pageids="|".join(map(str, ids[start : start + 50])),
                    prop="info|categories",
                    cllimit=500,
                    **continuation,
                )
                for page in result.get("query", {}).get("pages", []):
                    entry = batch.setdefault(page["pageid"], dict(page, categories=[]))
                    entry["categories"].extend(page.get("categories", []))
                continuation = result.get("continue", {})
                if not continuation:
                    break
                token = repr(sorted(continuation.items()))
                if token in seen:
                    raise CrawlError("Repeated description continuation")
                seen.add(token)
            pages.extend(batch.values())
        return pages

    def fetch(self, page):
        params = {"page": page["title"]}  # revid and HTML come from the same parse response
        item = self.api(action="parse", prop="text|sections|categories|images|revid", **params).get("parse", {})
        if not item.get("revid") or not isinstance(item.get("text"), str):
            raise CrawlError("Missing parsed HTML/revision")
        return {
            "schema_version": 1,
            "source": self.name,
            "source_id": str(item["pageid"]),
            "title": item["title"],
            "url": self.config["sources"]["wikigg"]["page_url"].format(
                title=quote(item["title"].replace(" ", "_"), safe="")
            ),
            "revision_id": item["revid"],
            "fetched_at": now(),
            "content_format": "html",
            "content": item["text"],
            "content_hash": sha256(item["text"].encode()),
            "categories": [x.get("category", x.get("*", "")) for x in item.get("categories", [])],
            "sections": item.get("sections", []),
            "image_titles": item.get("images", []),
            "license": self.config["sources"]["wikigg"]["license"],
            "scope_status": "requires_section_review",
            "game_scope": None,
        }

    def image_info(self, titles):
        output = {}
        titles = list(dict.fromkeys(titles))
        for start in range(0, len(titles), 40):
            result = self.api(
                action="query",
                titles="|".join(titles[start : start + 40]),
                prop="imageinfo",
                iiprop="url|size|mime|sha1|timestamp|extmetadata",
            )
            aliases = {x["to"]: x["from"] for x in result.get("query", {}).get("normalized", [])}
            for page in result.get("query", {}).get("pages", []):
                info = (page.get("imageinfo") or [{}])[0]
                output[page["title"]] = info
                output[aliases.get(page["title"], page["title"])] = info
        return output
