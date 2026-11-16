"""Cập nhật tăng dần (FR-ING-07): fake MediaWiki, fake index/DB/builder; không mạng, không model, không embedding.

Phụ trách: TV2 · [S5] Cập nhật dữ liệu tăng dần
"""

import pytest

from ingest.crawl.http import CrawlError
from ingest.sources.wikigg import WikiGG

CONFIG = {"sources": {"wikigg": {"api_url": "https://wiki.test/api.php", "page_url": "u/{title}", "license": "x"}}}


class Client:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def json(self, url):
        self.calls.append(url)
        return self.pages.pop(0)

    def sleep(self, seconds):
        pass


def test_recent_changes_follows_continuation_and_passes_since():
    client = Client(
        [
            {"query": {"recentchanges": [{"pageid": 1, "title": "A", "type": "edit"}]}, "continue": {"rccontinue": "x"}},
            {"query": {"recentchanges": [{"pageid": 2, "title": "B", "type": "new"}]}},
        ]
    )
    entries = WikiGG(client, CONFIG).recent_changes("2026-11-01T00:00:00+00:00")
    assert [e["pageid"] for e in entries] == [1, 2]
    assert "rcstart=2026-11-01T00%3A00%3A00%2B00%3A00" in client.calls[0] and "rccontinue=x" in client.calls[1]


def test_recent_changes_rejects_repeated_continuation():
    page = {"query": {"recentchanges": []}, "continue": {"rccontinue": "x"}}
    with pytest.raises(CrawlError):
        WikiGG(Client([dict(page), dict(page), dict(page)]), CONFIG).recent_changes("2026-11-01T00:00:00Z")
