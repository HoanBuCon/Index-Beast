"""Local image fixtures and fake RAG; no LLM, embedding, server DB or downloads."""

import asyncio
import csv
import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image

from app.api.deps import get_chat_service
from app.api.schemas.chat import ChatRequest
from app.services.images import ImageCatalog
from core.config import Settings
from tests.unit.test_live_chat import BODY, FakeLLM, FakeRetriever, hit, service


@pytest.fixture
def media(tmp_path):
    root = tmp_path / "blobs"
    catalog_path, docs_path, manifests = tmp_path / "images.csv", tmp_path / "docs.jsonl", tmp_path / "manifests"
    manifests.mkdir()
    rows, docs, hits, paths = [], [], [], []
    for n in range(1, 6):
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), (n * 30, 20, 30)).save(buffer, format="PNG")
        data = buffer.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        path = root / digest[:2] / (digest + ".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        paths.append(path)
        doc = {
            "source": "wikigg",
            "source_id": str(n),
            "revision_id": 10,
            "game_scope": "elden_ring",
            "release_scope": "unknown",
            "url": f"https://example.test/entity{n}",
        }
        docs.append(doc)
        rows.append(
            {
                "occurrence_id": f"occ-{n}",
                "source_id": str(n),
                "revision_id": "10",
                "section": "Infobox",
                "image_id": digest,
                "local_path": f"D:\\Producer\\media\\blobs\\{digest[:2]}\\{digest}.png",
                "caption": f"Caption {n}",
                "alt": f"Alt {n}",
                "source_url": "https://example.test/image.png",
                "description_url": "https://example.test/File:image.png",
                "license": "",
                "license_status": "unknown_review_required",
                "association": "exact_section",
                "media_status": "cached",
                "spoiler_level": "",
            }
        )
        hits.append(
            hit(n, **doc, review_status=None, section="Infobox", image_ids=[digest], image_association="section")
        )
        (manifests / f"{n}.json").write_text(
            json.dumps(
                {
                    "source": "wikigg",
                    "source_id": str(n),
                    "revision_id": 10,
                    "images": [{"image_id": digest, "status": "cached", "artist": "<a>Artist</a>", "license": None}],
                }
            ),
            encoding="utf-8",
        )

    def write():
        with catalog_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        docs_path.write_text("".join(json.dumps(d) + "\n" for d in docs), encoding="utf-8")

    write()
    settings = Settings(
        _env_file=None,
        rag_images_catalog=str(catalog_path),
        rag_images_documents=str(docs_path),
        rag_images_root=str(root),
        rag_images_manifests=str(manifests),
    )
    return SimpleNamespace(
        settings=settings,
        catalog=ImageCatalog(settings),
        rows=rows,
        docs=docs,
        hits=hits,
        paths=paths,
        write=write,
        root=root,
        manifests=manifests,
    )


async def test_exact_provenance_cited_only_dedup_and_limit(media):
    result = await media.catalog.resolve(media.hits, [2, 4], spoilers=True)
    assert [x.id for x in result.images] == [media.rows[1]["image_id"], media.rows[3]["image_id"]]
    assert result.images[0].source_indices == [2] and result.images[0].attribution == "Artist"
    assert result.images[0].license is None and result.images[0].license_status == "unknown_review_required"
    assert result.images[0].url.startswith("/api/v1/images/") and "Producer" not in result.images[0].model_dump_json()
    result = await media.catalog.resolve(media.hits, [1, 2, 3, 4, 5], spoilers=True)
    assert len(result.images) == 3 and result.reasons["image_limit"] == 2
    duplicated = [media.hits[0], replace(media.hits[0], id="other-hit")]
    result = await media.catalog.resolve(duplicated, [1, 2], spoilers=True)
    assert len(result.images) == 1 and result.images[0].source_indices == [1, 2]


@pytest.mark.parametrize("change", ["revision", "section", "scope", "release", "source", "association", "unrelated_id"])
async def test_never_borrows_same_hash_from_wrong_provenance(media, change):
    p = media.hits[0].payload
    if change == "revision":
        p["revision_id"] = 11
    elif change == "section":
        p["section"] = "Description"
    elif change == "scope":
        p["game_scope"] = "nightreign"
    elif change == "release":
        p["release_scope"] = "sote_candidate"
    elif change == "source":
        p["source"] = "another-source"
    elif change == "association":
        p["image_association"] = "page"
    else:
        p["image_ids"] = [media.rows[1]["image_id"]]
    assert (await media.catalog.resolve(media.hits, [1], spoilers=True)).images == []


async def test_spoilers_unknown_never_inferred_safe(media):
    media.hits[0].payload["spoiler_level"] = 0
    assert not (await media.catalog.resolve(media.hits, [1], spoilers=False)).images
    media.rows[0]["spoiler_level"] = "0"
    media.write()
    media.catalog = ImageCatalog(media.settings)
    assert len((await media.catalog.resolve(media.hits, [1], spoilers=False)).images) == 1


@pytest.mark.parametrize("change", ["excluded_ui", "review", "failed", "gallery", "traversal", "encoded", "svg"])
async def test_bad_rows_are_not_servable_or_selected(media, change):
    row = media.rows[0]
    if change in {"excluded_ui", "review"}:
        row["association"] = change
    elif change == "failed":
        row["media_status"] = "failed"
    elif change == "gallery":
        row["section"] = "Gallery"
        media.hits[0].payload["section"] = "Gallery"
    elif change == "traversal":
        row["local_path"] = "../" + media.paths[0].name
    elif change == "encoded":
        row["local_path"] = "%2e%2e/" + media.paths[0].name
    else:
        row["local_path"] = str(media.paths[0].with_suffix(".svg"))
    media.write()
    assert not (await media.catalog.resolve(media.hits, [1], spoilers=True)).images
    assert media.catalog.read_blob(row["image_id"])[0] is None


@pytest.mark.parametrize("change", ["missing", "tampered", "html_bytes", "size", "pixels"])
def test_file_verification_and_limits(media, change):
    path = media.paths[0]
    if change == "missing":
        path.unlink()
    elif change == "tampered":
        path.write_bytes(b"corrupt")
    elif change == "html_bytes":
        data = b"<html>not an image</html>"
        digest = hashlib.sha256(data).hexdigest()
        new = media.root / digest[:2] / (digest + ".png")
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_bytes(data)
        media.rows[0].update(image_id=digest, local_path=str(new))
        media.write()
    elif change == "size":
        media.catalog.max_bytes = 10
    else:
        media.catalog.max_pixels = 10
    assert media.catalog.read_blob(media.rows[0]["image_id"])[0] is None


def test_resolved_symlink_or_junction_outside_root_is_rejected(media, monkeypatch, tmp_path):
    target = media.paths[0]
    outside = tmp_path / "outside.png"
    outside.write_bytes(target.read_bytes())
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        return outside if path == target else original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    assert media.catalog.read_blob(media.rows[0]["image_id"])[1] == "outside_media_root"


def test_endpoint_bytes_mime_etag_and_not_found(client, media):
    client.app.state.image_catalog = media.catalog
    url = "/api/v1/images/" + media.rows[0]["image_id"]
    response = client.get(url)
    assert response.status_code == 200 and response.content == media.paths[0].read_bytes()
    assert response.headers["content-type"] == "image/png" and response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert client.get(url, headers={"If-None-Match": response.headers["etag"]}).status_code == 304
    for invalid in ("unknown", "a" * 64, "%2e%2e%2f.env", "..%252f.env"):
        assert client.get("/api/v1/images/" + invalid).status_code == 404
    media.paths[0].write_bytes(b"changed after initial read")
    assert client.get(url, headers={"If-None-Match": response.headers["etag"]}).status_code == 404


def configure_chat(client, media, llm=None, mode="rag"):
    llm = llm or FakeLLM()
    live = service(mode, llm, FakeRetriever(media.hits))
    live.image_catalog = media.catalog
    client.app.dependency_overrides[get_chat_service] = lambda: live
    return live, llm


def test_json_sse_history_and_three_modes_remain_compatible(client, media):
    live, llm = configure_chat(client, media)
    response = client.post("/api/v1/chat", json=BODY)
    assert response.status_code == 200
    data = response.json()
    assert len(data["images"]) == 1 and data["images"][0]["source_indices"] == [1]
    history = live.history(UUID(data["conversation_id"]))
    assert history.messages[-1].images[0].id == data["images"][0]["id"]
    llm.tokens = list(json.dumps(llm.data))
    response = client.post("/api/v1/chat/stream", json=BODY)
    frames = [(f.splitlines()[0], json.loads(f.split("data: ", 1)[1])) for f in response.text.strip().split("\n\n")]
    sources = next(p for event, p in frames if event == "event: sources")
    assert sources["images"] == data["images"] and frames[-1][0] == "event: done"
    assert "event: images" not in response.text
    assert all("images" not in p for event, p in frames if event == "event: token")
    configure_chat(client, media, mode="llm_only")
    assert client.post("/api/v1/chat", json=BODY).json()["images"] == []
    client.app.dependency_overrides.clear()
    assert client.post("/api/v1/chat", json=BODY).json()["images"] == []  # Fixture app defaults mock.


def test_generation_failure_and_no_evidence_never_resolve_images(client, media, monkeypatch):
    live, llm = configure_chat(client, media)

    async def forbidden(*args, **kwargs):
        pytest.fail("Resolver called for invalid/ungrounded answer")

    monkeypatch.setattr(media.catalog, "resolve", forbidden)
    llm.data["evidence"] = []
    assert client.post("/api/v1/chat", json=BODY).status_code == 502
    llm.tokens = list(json.dumps({**llm.data, "answer": "Ranni [1]. Another supported sentence [1]."}))
    stream = client.post("/api/v1/chat/stream", json=BODY)
    assert "event: done" not in stream.text and "images" not in stream.text
    llm.data = {"answer": "Evidence is missing.", "evidence": [], "insufficient": True}
    assert client.post("/api/v1/chat", json=BODY).json()["images"] == []


def test_missing_catalog_and_resolver_errors_fall_back_to_text(client, media, monkeypatch):
    live, _ = configure_chat(client, media)
    media.catalog.catalog_path = Path("missing-catalog.csv")
    assert client.post("/api/v1/chat", json=BODY).json()["images"] == []

    async def broken(*args, **kwargs):
        raise OSError("private path")

    monkeypatch.setattr(media.catalog, "resolve", broken)
    response = client.post("/api/v1/chat", json=BODY)
    assert response.status_code == 200 and response.json()["images"] == [] and "private path" not in response.text


async def test_catalog_is_lazy_cached_and_has_no_model_or_network_clients(media, monkeypatch):
    import httpx
    from qdrant_client import AsyncQdrantClient

    from app.adapters.llm import DeepSeekLLM
    from core.encoders.onnx import FastEmbedEncoder

    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected model/client creation")

    for cls in (httpx.Client, httpx.AsyncClient, AsyncQdrantClient, DeepSeekLLM, FastEmbedEncoder):
        monkeypatch.setattr(cls, "__init__", forbidden)
    original, scans = Path.open, []

    def opened(path, *args, **kwargs):
        if path == media.catalog.catalog_path:
            scans.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    catalog = ImageCatalog(media.settings)
    assert not scans
    assert len((await catalog.resolve(media.hits, [1], spoilers=True)).images) == 1
    assert len((await catalog.resolve(media.hits, [1], spoilers=True)).images) == 1
    assert len(scans) == 1


@pytest.mark.parametrize("streaming", [False, True])
async def test_image_resolution_cancellation_is_not_swallowed(media, streaming):
    llm = FakeLLM()
    llm.tokens = list(json.dumps(llm.data))
    live = service("rag", llm, FakeRetriever(media.hits))
    started = asyncio.Event()

    class Slow:
        async def resolve(self, *args, **kwargs):
            started.set()
            await asyncio.Event().wait()

    live.image_catalog = Slow()
    events = None
    if streaming:
        events = await live.open_stream(ChatRequest(**BODY))

        async def consume():
            return [frame async for frame in events]

        task = asyncio.create_task(consume())
    else:
        task = asyncio.create_task(live.answer(ChatRequest(**BODY)))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    if events is not None:
        await events.aclose()
    assert not live.traces and not next(iter(live._conversations.values())).lock.locked()


async def test_wrong_revision_manifest_does_not_invent_attribution(media):
    path = media.manifests / "1.json"
    doc = json.loads(path.read_text())
    doc["revision_id"] = 999
    path.write_text(json.dumps(doc), encoding="utf-8")
    result = await media.catalog.resolve(media.hits, [1], spoilers=True)
    assert result.images[0].attribution is None and result.images[0].license_status == "unknown_review_required"


async def test_same_blob_does_not_merge_release_contexts(media):
    shared = media.rows[0]["image_id"]
    media.rows[1].update(image_id=shared, local_path=media.rows[0]["local_path"])
    media.docs[1]["release_scope"] = "sote_candidate"
    media.hits[1].payload.update(image_ids=[shared], release_scope="sote_candidate")
    media.write()
    result = await media.catalog.resolve(media.hits, [1, 2], spoilers=True)
    assert len(result.images) == 1 and result.images[0].source_indices == [1]
    assert result.images[0].release_scope == "unknown" and result.reasons["dedup_scope_conflict"] == 1


async def test_images_can_be_disabled_without_opening_any_artifacts(media, monkeypatch):
    media.settings.rag_images_enabled = False
    catalog = ImageCatalog(media.settings)

    def forbidden(*args, **kwargs):
        pytest.fail("I/O for disabled image feature")

    monkeypatch.setattr(Path, "open", forbidden)
    assert (await catalog.resolve(media.hits, [1], spoilers=True)).images == []
    assert catalog.read_blob(media.rows[0]["image_id"])[0] is None


def test_hash_matching_but_truncated_jpeg_is_not_served(media):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "blue").save(buffer, format="JPEG")
    data = buffer.getvalue()[:-20]
    # Headers can still be parsed, so hash/MIME/header checks alone are insufficient.
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG"
    digest = hashlib.sha256(data).hexdigest()
    path = media.root / digest[:2] / (digest + ".jpg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    media.rows[0].update(image_id=digest, local_path=str(path))
    media.write()
    assert media.catalog.read_blob(digest)[0] is None


@pytest.mark.parametrize(
    "format_name,extension,mime",
    [
        ("PNG", ".png", "image/png"),
        ("JPEG", ".jpg", "image/jpeg"),
        ("WEBP", ".webp", "image/webp"),
        ("GIF", ".gif", "image/gif"),
    ],
)
def test_endpoint_uses_verified_raster_mime(client, media, format_name, extension, mime):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "red").save(buffer, format=format_name)
    data = buffer.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    path = media.root / digest[:2] / (digest + extension)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    media.rows[0].update(image_id=digest, local_path=str(path))
    media.write()
    client.app.state.image_catalog = media.catalog
    response = client.get("/api/v1/images/" + digest)
    assert response.status_code == 200 and response.content == data and response.headers["content-type"] == mime
