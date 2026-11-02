"""Offline regression checks for the S1 crawler and media contracts."""

import io
from collections import Counter
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from ingest.artifacts import sha256
from ingest.crawl.http import CrawlError, HttpClient
from ingest.crawl.media import MediaStore, image_occurrences, verify_image
from ingest.crawl.runner import crawl
from ingest.settings import load_settings
from ingest.sources.wikigg import WikiGG


@pytest.fixture
def config(tmp_path):
    c = load_settings()
    c["data_dir"] = tmp_path
    c["crawl"]["contact_email"] = "test@example.org"
    c["crawl"]["allowed_hosts"] = ["example.org"]
    c["crawl"]["max_retries"] = 1
    return c


def png():
    b = io.BytesIO()
    Image.new("RGB", (80, 90), "blue").save(b, format="PNG")
    return b.getvalue()


def test_http_pacing_retry_and_robots(config):
    ticks = [0.0]
    calls = []
    attempts = Counter()

    def sleep(n):
        ticks[0] += n

    def handler(request):
        calls.append((request.url.path, ticks[0]))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /blocked\n")
        attempts[request.url.path] += 1
        if attempts[request.url.path] == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"ok": True})

    client = HttpClient(config, transport=httpx.MockTransport(handler), sleep=sleep, clock=lambda: ticks[0])
    assert client.json("https://example.org/page") == {"ok": True}
    with pytest.raises(CrawlError, match="disallows"):
        client.get("https://example.org/blocked")
    assert all(b[1] - a[1] >= 1 for a, b in zip(calls, calls[1:], strict=False))
    assert client.stats["retries"] == 1
    assert "/blocked" not in [p for p, t in calls]
    client.close()


def test_redirect_host_and_response_limits(config):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/big":
            return httpx.Response(200, content=b"a" * 100)
        return httpx.Response(302, headers={"Location": "https://untrusted.example/file"})

    client = HttpClient(config, transport=httpx.MockTransport(handler), sleep=lambda n: None)
    with pytest.raises(CrawlError, match="outside"):
        client.get("https://example.org/redirect")
    with pytest.raises(CrawlError, match="byte limit"):
        client.get("https://example.org/big", max_bytes=10)
    client.close()


def test_category_continuation_and_dedup(config):
    source = WikiGG(None, config)
    calls = []

    def api(**kwargs):
        calls.append(kwargs)
        p = {"pageid": 1, "title": "A", "ns": 0}
        if len(calls) == 1:
            return {"query": {"categorymembers": [p]}, "continue": {"continue": "-||", "cmcontinue": "next"}}
        return {"query": {"categorymembers": [p, {"pageid": 2, "title": "B", "ns": 0}]}}

    source.api = api
    assert len(source.list_category("NPC")) == 2
    assert calls[1]["cmcontinue"] == "next" and calls[1]["continue"] == "-||"


def test_revision_is_from_parse_response(config):
    source = WikiGG(None, config)
    calls = []

    def api(**kwargs):
        calls.append(kwargs)
        return {"parse": {"pageid": 1, "title": "A", "revid": 44, "text": "<p>lore</p>"}}

    source.api = api
    raw = source.fetch({"pageid": 1, "title": "A", "lastrevid": 44})
    assert calls[0]["page"] == "A"
    assert raw["revision_id"] == 44
    assert raw["content_hash"] == sha256(raw["content"].encode())
    assert raw["game_scope"] is None


def test_media_occurrences_preserve_context_and_tabs():
    raw = {
        "url": "https://example.org/wiki/A",
        "content": """<div class="mw-parser-output">
    <div class="navbox"><img src="/nav.png"></div><h2>Lore</h2>
    <figure><a href="/wiki/File:A.png"><img src="/a.png" alt="portrait" width="100"></a>
    <figcaption>Character A</figcaption></figure>
    <h3>Dialogue</h3><div style="display:none"><a href="/wiki/File:A.png"><img src="/a.png"></a></div>
    <img src="/icon.png" width="16" height="16"></div>""",
    }
    images = image_occurrences(raw)
    assert len(images) == 3
    assert images[0]["caption"] == "Character A" and images[0]["section"] == "Lore"
    assert images[1]["section"] == "Lore > Dialogue"
    assert images[2]["status"] == "excluded"


def test_image_validation(config):
    assert verify_image(png(), "image/png", config["media"])[1] == (80, 90)
    with pytest.raises(CrawlError):
        verify_image(b"<html>challenge</html>", "image/png", config["media"])
    assert verify_image(png(), "image/webp", config["media"])[0] == ".png"
    with pytest.raises(CrawlError):
        verify_image(png(), "image/png", dict(config["media"], max_pixels=10))


def test_blob_dedup_cache_and_corruption(config):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, content=png(), headers={"content-type": "image/png"})

    store = MediaStore(SimpleNamespace(get=get), config)
    a = store.download("https://example.org/a", "rev1")
    assert store.download("https://example.org/a", "rev1")["status"] == "cached"
    b = store.download("https://example.org/b", "rev1")
    assert a["path"] == b["path"] and len(calls) == 2
    (config["data_dir"] / a["path"]).write_bytes(b"corrupt")
    store.download("https://example.org/a", "rev1")
    assert len(calls) == 3
    assert (config["data_dir"] / a["path"]).read_bytes() == png()


def test_crawl_resume_no_refetch(config):
    candidate = {"pageid": 1, "title": "Test", "lastrevid": 12}
    source = SimpleNamespace(
        name="wikigg", client=SimpleNamespace(stats={}), api=lambda **kw: {"query": {"pages": [candidate]}}
    )
    calls = []

    def fetch(page):
        calls.append(page)
        return {
            "source_id": "1",
            "title": "Test",
            "revision_id": 12,
            "content": "lore",
            "content_hash": sha256(b"lore"),
        }

    source.fetch = fetch
    first = crawl(source, config, 1, page="Test", with_media=False)
    second = crawl(source, config, 1, page="Test", with_media=False)
    assert first["status"] == second["status"] == "completed"
    assert len(calls) == 1 and second["counts"]["cache_hits"] == 1
    candidate["lastrevid"] = 13
    crawl(source, config, 1, page="Test", with_media=False)
    assert len(calls) == 2


def test_scope_excludes_dlc_lead_but_not_later_section():
    from ingest.crawl.scope import sample_scope_reason

    assert sample_scope_reason({"title": "Bayle", "content": "<p>An optional boss in Shadow of the Erdtree.</p>"})
    assert sample_scope_reason({"title": "Village", "content": "<p>A place in the Gravesite Plain.</p>"})
    assert sample_scope_reason(
        {"title": "Woods", "content": '<aside class="portable-infobox">Scadu Altus</aside><p>Forest.</p>'}
    )
    assert (
        sample_scope_reason({"title": "Melina", "content": "<p>A base-game NPC who guides the Tarnished.</p>"}) is None
    )


def test_media_manifest_tracks_failed_download_without_losing_provenance(config):
    from ingest.crawl.media import MediaStore

    class FakeSource:
        name = "wikigg"

        def image_info(self, titles):
            return {"File:A.png": {"url": "https://example.org/a.png", "extmetadata": {}}}

    def fail(url, **kw):
        raise CrawlError("HTTP 403")

    raw = {
        "source_id": "1",
        "url": "https://example.org/wiki/A",
        "revision_id": 2,
        "content": '<h2>Lore</h2><a href="/wiki/File:A.png"><img src="/a.png" alt="A"></a>',
    }
    result = MediaStore(SimpleNamespace(get=fail), config).page(FakeSource(), raw)
    assert result["status"] == "completed_with_errors"
    item = result["images"][0]
    assert item["section"] == "Lore" and item["status"] == "failed"
    assert item["license_status"] == "unknown_review_required"
    assert item["file_title"] == "File:A.png"


def test_empty_category_batch_with_continue_is_not_end(config):
    source = WikiGG(None, config)
    responses = iter(
        [
            {"query": {"categorymembers": []}, "continue": {"cmcontinue": "next", "continue": "-||"}},
            {"query": {"categorymembers": [{"pageid": 9, "ns": 0, "title": "A"}]}},
        ]
    )
    source.api = lambda **kw: next(responses)
    assert source.list_category("NPC")[0]["pageid"] == 9


def test_image_context_skips_infobox_headings_and_rating_icons():
    raw = {
        "url": "https://example.org/wiki/A",
        "content": """<div class="mw-parser-output">
    <aside class="portable-infobox"><h2>A</h2><img src="/portrait.png"></aside>
    <p>Intro</p><img src="/intro.png"><h2>Lore</h2>
    <img src="/ER_Menu_Icon_Message_Rating_5.png" width="45" height="45"></div>""",
    }
    images = image_occurrences(raw)
    assert images[0]["section"] == "Infobox"
    assert images[1]["section"] == "Introduction"
    assert images[2]["status"] == "excluded" and images[2]["reason"] == "interface_rating_icon"
