"""Test với model/tải xuống giả: chọn ID và gắn kết không phải là đo độ chính xác hình ảnh."""

import hashlib
import io
import json
import socket
from types import SimpleNamespace

import pytest
from langchain_core.runnables import RunnableLambda
from PIL import Image

from app.adapters.llm import LLMResponse
from app.adapters.tavily import WebHit
from app.api.schemas.chat import ChatImage, ChatRequest, Source
from app.rag.generator import Generated, Prepared
from app.services import answer_media as module
from app.services import images
from tests.unit.test_images import media as media


def source(h, index=1):
    return Source(index=index, title=h.payload["title"], url=h.payload["url"])


class Model:
    def __init__(self, choose):
        self.choose = choose
        self.payload = None

    def bind_model(self, **kw):
        return RunnableLambda(lambda x: x)

    async def invoke_chain(self, chain, inputs):
        self.payload = json.loads(inputs["question"])
        return LLMResponse(json.dumps({"ids": self.choose(self.payload["candidates"])}), "fake", 1, 1, "stop")


def setup(media, choose, hits=None):
    llm = Model(choose)
    service = SimpleNamespace(image_catalog=media.catalog, pipeline=SimpleNamespace(llm=llm))
    p = Prepared("rag", "vi", [], hits=hits or media.hits, max_calls=6)
    answer = Generated("Câu trả lời [1].", sources=[source(p.hits[0])], grounded=True)
    return service, p, answer, llm


async def test_model_selects_entity_main_image_from_same_page_other_section(media):
    media.hits[0].payload["section"] = "Description"
    service, p, answer, llm = setup(media, lambda rows: [rows[0]["id"]])
    result = await module.resolve(service, ChatRequest(message="Ranni", channel="web"), p, answer)
    assert result[0].association == "entity_page" and result[0].source_indices == [1]
    assert result[0].attribution == "Artist" and result[0].license is None
    assert llm.payload["candidates"][0]["association"] == "entity_page"
    assert len(p.trace["model_calls"]) == 1


@pytest.mark.parametrize("change", ["source_id", "revision_id", "release_scope"])
def test_page_association_never_borrows_other_revision_or_release(media, change):
    media.hits[0].payload[change] = "different"
    assert module.candidates(media.catalog, media.hits, [source(media.hits[0])]) == {}


async def test_abstain_or_forged_ids(media):
    service, p, answer, _ = setup(media, lambda rows: [])
    assert await module.resolve(service, ChatRequest(message="Rivers of Blood", channel="web"), p, answer) == []
    service, p, answer, _ = setup(media, lambda rows: ["invented"])
    with pytest.raises(ValueError):
        await module.resolve(service, ChatRequest(message="Rivers of Blood", channel="web"), p, answer)


def test_menu_icons_are_not_candidates(media):
    media.rows[0]["alt"] = "ER Inventory Menu Icon Equipment.png"
    media.write()
    assert module.candidates(media.catalog, media.hits, [source(media.hits[0])]) == {}


async def test_web_selection_download_error_does_not_erase_text(media, monkeypatch):
    web = WebHit(
        "web1",
        0,
        {
            **media.hits[0].payload,
            "web_images": [{"url": "https://static0.fextralifeimages.com/a.png", "description": "Ranni"}],
        },
    )
    service, p, answer, llm = setup(media, lambda rows: [rows[0]["id"]], [web])

    def bad(*a):
        raise OSError("download failed")

    monkeypatch.setattr(module, "download", bad)
    assert await module.resolve(service, ChatRequest(message="Ranni", channel="web"), p, answer) == []
    assert answer.answer == "Câu trả lời [1]."
    assert llm.payload["candidates"][0]["association"] == "web_result"


async def test_image_budget_preserved_and_legacy_spoiler_flag_allows_selection(media):
    service, p, answer, llm = setup(media, lambda rows: pytest.fail("must not call"))
    p.max_calls = 0
    assert await module.resolve(service, ChatRequest(message="Ranni", channel="web"), p, answer) == []
    service, p, answer, llm = setup(media, lambda rows: [])
    assert (
        await module.resolve(
            service, ChatRequest(message="Ranni", channel="web", options={"spoilers": False}), p, answer
        )
        == []
    )
    assert llm.payload["candidates"]


@pytest.mark.parametrize(
    "url",
    [
        "http://eldenring.wiki.gg/a.png",
        "https://evil.test/a.png",
        "https://user@eldenring.wiki.gg/a.png",
        "https://eldenring.wiki.gg:8443/a.png",
    ],
)
def test_download_url_allowlist(url, tmp_path):
    with pytest.raises(ValueError):
        module.download(url, tmp_path)


def test_private_dns_is_rejected_before_connect(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: pytest.fail("private connection"))
    with pytest.raises(ValueError, match="non_public"):
        module.download("https://eldenring.wiki.gg/a.png", tmp_path)


@pytest.mark.parametrize("fault", [None, "mime", "status", "bytes", "decode"])
def test_public_pinned_fetch_cache_and_serving(media, tmp_path, monkeypatch, fault):
    raw = media.paths[0].read_bytes()
    if fault == "bytes":
        raw = b"x" * 5_000_001
    if fault == "decode":
        raw = b"not an image"
    stream = io.BytesIO(raw)
    response = SimpleNamespace(
        status=302 if fault == "status" else 200,
        getheader=lambda *a: "text/html" if fault == "mime" else "image/png",
        read1=stream.read,
    )
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("8.8.8.8", 443))])
    connected = []
    monkeypatch.setattr(socket, "create_connection", lambda addr, **kw: connected.append(addr) or object())
    monkeypatch.setattr(
        module.ssl, "create_default_context", lambda: SimpleNamespace(wrap_socket=lambda sock, server_hostname: sock)
    )

    # HTTPSConnection.__init__ cần các thuộc tính SSL context; dùng một lớp cơ sở giả nhỏ tương thích.
    class Connection:
        def __init__(self, host, timeout, context):
            self.host = host
            self.timeout = timeout
            self._context = context

        def request(self, *a, **kw):
            self.connect()

        def getresponse(self):
            return response

        def close(self):
            pass

    monkeypatch.setattr(module.http.client, "HTTPSConnection", Connection)
    if fault:
        with pytest.raises((ValueError, OSError)):
            module.download("https://eldenring.wiki.gg/a.png", tmp_path)
        assert not list(tmp_path.glob("*/*.png"))
    else:
        digest = module.download("https://eldenring.wiki.gg/a.png", tmp_path)
        assert connected == [("8.8.8.8", 443)]
        assert digest == hashlib.sha256(raw).hexdigest()
        monkeypatch.setattr(images, "CACHE", tmp_path)
        # Catalog ID khác để chạy đường cache web thay vì blob local gốc.
        buffer = io.BytesIO()
        Image.new("RGB", (5, 6), "blue").save(buffer, "PNG")
        webraw = buffer.getvalue()
        webid = hashlib.sha256(webraw).hexdigest()
        path = tmp_path / webid[:2] / (webid + ".png")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(webraw)
        blob, error = media.catalog.read_blob(webid)
        assert error is None and blob.mime == "image/png" and blob.data == webraw
        path.write_bytes(b"corrupt")
        assert media.catalog.read_blob(webid)[0] is None


async def test_duplicate_blob_and_successful_web_association(media, monkeypatch):
    from dataclasses import replace

    hits = [media.hits[0], replace(media.hits[0], id="duplicate")]
    assert len(module.candidates(media.catalog, hits, [source(hits[0], 1), source(hits[1], 2)])) == 1
    web = WebHit(
        "web",
        0,
        {
            **hits[0].payload,
            "web_images": [{"url": "https://eldenring.wiki.gg/images/main.png", "description": "Ranni"}],
        },
    )
    service, p, answer, llm = setup(media, lambda rows: [rows[0]["id"]], [web])
    monkeypatch.setattr(module, "download", lambda url: media.rows[0]["image_id"])
    result = await module.resolve(service, ChatRequest(message="Ranni", channel="web"), p, answer)
    assert len(result) == 1 and result[0].association == "web_result"
    assert result[0].source_url == answer.sources[0].url and result[0].license is None
    assert result[0].license_status == "unknown_review_required"


async def test_image_selection_cancellation_propagates(media):
    import asyncio

    service, p, answer, llm = setup(media, lambda rows: [])
    started = asyncio.Event()

    async def block(*args):
        started.set()
        await asyncio.Future()

    llm.invoke_chain = block
    task = asyncio.create_task(module.resolve(service, ChatRequest(message="Ranni", channel="web"), p, answer))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def image(index):
    digest = hashlib.sha256(str(index).encode()).hexdigest()
    return ChatImage(id=digest, url=f"/api/v1/images/{digest}", source_url="https://x", source_indices=[index])


@pytest.mark.parametrize("grounded", [True, False])
async def test_parallel_image_selection_keeps_only_images_of_cited_sources(media, grounded):
    # 23/11: ảnh được chọn song song với bước viết trên evidence Agent đã chọn, sau đó lọc theo nguồn được trích dẫn.
    import asyncio

    from app.services.chat import LiveChatService

    svc = LiveChatService.__new__(LiveChatService)
    svc.image_catalog = media.catalog
    seen = {}

    async def fake_images(req, prepared, result, started=None, limit=None):
        seen["sources"] = [s.index for s in result.sources]
        await asyncio.sleep(0)
        prepared.trace["images"] = {"returned": 2, "selection": "model_metadata"}
        return [image(1), image(2)]

    svc._images = fake_images
    p = Prepared("rag", "vi", [], hits=media.hits[:1] * 2)
    req = ChatRequest(message="Ranni", channel="web")
    task = svc._start_images(req, p, None)
    cited = [Source(index=2, title="Ranni", url="https://x")] if grounded else []
    images = await svc._finish_images(task, req, p, Generated("Ranni [2].", sources=cited, grounded=grounded))
    if grounded:
        assert seen["sources"] == [1, 2] and [i.source_indices for i in images] == [[2]]
        assert p.trace["images"] == {"returned": 1, "selection": "model_metadata", "parallel": True}
    else:
        assert images == [] and task.done() and "images" not in p.trace


async def test_parallel_selection_falls_back_to_cited_sources_when_nothing_is_left(media):
    from app.services.chat import LiveChatService

    svc = LiveChatService.__new__(LiveChatService)
    svc.image_catalog = media.catalog
    calls = []

    async def fake_images(req, prepared, result, started=None, limit=None):
        calls.append([s.index for s in result.sources])
        prepared.trace["images"] = {"returned": 1, "selection": "model_metadata"}
        return [image(1)] if len(calls) == 1 else [image(2)]

    svc._images = fake_images
    p = Prepared("rag", "vi", [], hits=media.hits[:1] * 2)
    req = ChatRequest(message="Ranni", channel="web")
    task = svc._start_images(req, p, None)
    result = Generated("Ranni [2].", sources=[Source(index=2, title="Ranni", url="https://x")], grounded=True)
    images = await svc._finish_images(task, req, p, result)
    assert calls == [[1, 2], [2]] and [i.source_indices for i in images] == [[2]]
    assert p.trace["images"]["parallel"] == "fallback"
