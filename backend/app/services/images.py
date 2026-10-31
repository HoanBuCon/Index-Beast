"""Read-only TV2 image catalog and cited-section resolver. No model/network/DB dependencies.

TV2 full artifact contract: image_id = blob SHA-256, occurrence_id identifies page occurrences.
Absolute producer paths are relocated ONLY to the configured content-addressed blob root.
"""

import asyncio
import csv
import hashlib
import io
import json
import logging
import re
import threading
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError

from app.api.schemas.chat import ChatImage
from core.config import REPO_ROOT
from core.corpus import CorpusPolicy

IDENTIFIER = re.compile(r"^[0-9a-f]{64}$")
FORMATS = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"),
    "GIF": (".gif", "image/gif"),
}


def http_url(value):
    if not isinstance(value, str):
        return None
    try:
        p = urlsplit(value)
    except ValueError:
        return None
    return value if p.scheme in {"https", "http"} and p.netloc and not p.username and not p.password else None


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    if not isinstance(value, str) or not value.strip():
        return None
    parser = PlainText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())[:2000] or None


@dataclass(frozen=True)
class Blob:
    data: bytes
    mime: str
    extension: str


@dataclass
class Resolution:
    images: list[ChatImage]
    reasons: dict[str, int]


class ImageCatalog:
    def __init__(self, settings):
        self.enabled = settings.rag_images_enabled
        self.policy = CorpusPolicy.from_settings(settings)
        base = REPO_ROOT / "backend"
        self.catalog_path = base / settings.rag_images_catalog
        self.documents_path = base / settings.rag_images_documents
        self.root = base / settings.rag_images_root
        self.manifests = base / settings.rag_images_manifests
        self.max_bytes, self.max_pixels = settings.rag_images_max_bytes, settings.rag_images_max_pixels
        self._lock = threading.Lock()
        self._loaded = False
        self._links = defaultdict(list)
        self._blobs = {}
        self.counts = Counter()
        self._metadata = lru_cache(maxsize=64)(self._read_metadata)

    def _load(self):
        if self._loaded or not self.enabled:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                documents = {}
                with self.documents_path.open(encoding="utf-8-sig") as stream:
                    for line in stream:
                        doc = json.loads(line)
                        if doc.get("source") != "wikigg" or doc.get("game_scope") not in self.policy.scopes:
                            continue
                        key = (str(doc["source_id"]), str(doc["revision_id"]))
                        if key in documents:
                            raise ValueError("Duplicate document provenance")
                        documents[key] = doc
                with self.catalog_path.open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    required = {
                        "occurrence_id",
                        "source_id",
                        "revision_id",
                        "section",
                        "image_id",
                        "local_path",
                        "association",
                        "media_status",
                    }
                    if (
                        not reader.fieldnames
                        or len(reader.fieldnames) != len(set(reader.fieldnames))
                        or not required <= set(reader.fieldnames)
                    ):
                        raise ValueError("Invalid image catalog columns")
                    for row in reader:
                        self.counts["rows"] += 1
                        if None in row or any(v is None for v in row.values()):
                            raise ValueError("Image catalog column mismatch")
                        if row["association"] != "exact_section" or any(
                            section.strip().casefold() in {"gallery", "references"}
                            for section in row["section"].split(">")
                        ):
                            self.counts["association_not_admitted"] += 1
                            continue
                        if row["media_status"] not in {"downloaded", "cached"}:
                            self.counts["download_not_available"] += 1
                            continue
                        if row.get("review_status") in {"rejected", "excluded"}:
                            self.counts["image_review_rejected"] += 1
                            continue
                        doc = documents.get((row["source_id"], row["revision_id"]))
                        if doc is None or not IDENTIFIER.fullmatch(row["image_id"]):
                            self.counts["invalid_provenance_or_id"] += 1
                            continue
                        path = self._relocated_path(row)
                        if path is None:
                            self.counts["invalid_path"] += 1
                            continue
                        row = {**row, "document": doc, "blob_path": path}
                        key = (row["source_id"], row["revision_id"], row["section"], row["image_id"])
                        self._links[key].append(row)
                        self._blobs.setdefault(row["image_id"], path)
                        self.counts["eligible_occurrences"] += 1
                for rows in self._links.values():
                    rows.sort(key=lambda r: r["occurrence_id"])
                self.counts["eligible_blobs"] = len(self._blobs)
            except (OSError, ValueError, KeyError, TypeError, csv.Error):
                self._links.clear()
                self._blobs.clear()
                self.counts["catalog_unavailable"] += 1
                logging.getLogger(__name__).warning("Image catalog unavailable; text chat remains enabled")
            self._loaded = True  # Restart application to reload/repair catalog; no scan per request.

    def _relocated_path(self, row):
        raw = row["local_path"]
        parts = PureWindowsPath(raw.replace("/", "\\")).parts
        filename = PureWindowsPath(raw).name
        if (
            ".." in parts
            or unquote(raw) != raw
            or "\x00" in raw
            or Path(filename).stem != row["image_id"]
            or Path(filename).suffix.lower() not in {v[0] for v in FORMATS.values()}
        ):
            return None
        return self.root / row["image_id"][:2] / filename

    def read_blob(self, image_id):
        if not self.enabled or not IDENTIFIER.fullmatch(image_id):
            return None, "unknown_image"
        self._load()
        path = self._blobs.get(image_id)
        if path is None:
            return None, "unknown_image"
        try:
            root, resolved = self.root.resolve(), path.resolve()
            if not resolved.is_relative_to(root):
                return None, "outside_media_root"
            if not resolved.is_file():
                return None, "missing_file"
            if resolved.stat().st_size > self.max_bytes:
                return None, "file_too_large"
            with resolved.open("rb") as stream:
                data = stream.read(self.max_bytes + 1)
            if len(data) > self.max_bytes or hashlib.sha256(data).hexdigest() != image_id:
                return None, "size_or_hash_mismatch"
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format not in FORMATS or image.width * image.height > self.max_pixels:
                        return None, "format_or_pixel_limit"
                    extension, mime = FORMATS[image.format]
                    if resolved.suffix.lower() != extension:
                        return None, "format_extension_mismatch"
                    image.verify()
                # JPEG.verify alone does not decode pixels; catch truncated/corrupt raster data too.
                # GIF validation covers the first frame, with the same byte/pixel caps.
                with Image.open(io.BytesIO(data)) as decoded:
                    decoded.load()
            return Blob(data, mime, extension), None
        except (
            OSError,
            ValueError,
            SyntaxError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            return None, "invalid_or_missing_image"

    def _read_metadata(self, source_id, revision_id, image_id):
        if not source_id.isdecimal():
            return {}
        try:
            path = (self.manifests / f"{source_id}.json").resolve()
            if not path.is_relative_to(self.manifests.resolve()) or path.stat().st_size > 2000000:
                return {}
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if (
                str(data.get("source_id")) != source_id
                or str(data.get("revision_id")) != revision_id
                or data.get("source") != "wikigg"
            ):
                return {}
            for row in data.get("images", []):
                if row.get("image_id") == image_id and row.get("status") in {"downloaded", "cached"}:
                    return {"attribution": plain(row.get("artist")), "license": plain(row.get("license"))}
        except (OSError, ValueError, TypeError, KeyError):
            pass
        return {}

    async def resolve(self, hits, source_indices, *, spoilers):
        return await asyncio.to_thread(self._resolve, hits, source_indices, spoilers)

    def _resolve(self, hits, source_indices, spoilers):
        if not self.enabled:
            return Resolution([], {"disabled": 1})
        self._load()
        reasons, images = Counter(), {}
        if self.counts.get("catalog_unavailable"):
            return Resolution([], {"catalog_unavailable": 1})
        examined = 0
        for index in sorted(set(source_indices)):
            if not 1 <= index <= len(hits):
                continue
            p = hits[index - 1].payload
            if (
                self.policy.exclusion_reason(p, spoilers=spoilers)
                or p.get("source") != "wikigg"
                or p.get("image_association") != "section"
            ):
                reasons["chunk_not_admitted_or_linked"] += 1
                continue
            image_ids = p.get("image_ids")
            if not isinstance(image_ids, list):
                reasons["invalid_image_ids"] += 1
                continue
            for image_id in image_ids:
                if not isinstance(image_id, str) or not IDENTIFIER.fullmatch(image_id):
                    reasons["invalid_image_id"] += 1
                    continue
                rows = self._links.get(
                    (str(p.get("source_id")), str(p.get("revision_id")), p.get("section"), image_id), []
                )
                if not rows:
                    reasons["no_exact_section_link"] += 1
                    continue
                row = rows[0]
                doc = row["document"]
                if doc.get("game_scope") != p.get("game_scope") or doc.get("release_scope") != p.get("release_scope"):
                    reasons["scope_mismatch"] += 1
                    continue
                if not spoilers and row.get("spoiler_level") != "0":
                    reasons["image_spoiler_unknown"] += 1
                    continue
                if image_id in images:
                    if images[image_id].game_scope != p.get("game_scope") or images[image_id].release_scope != p.get(
                        "release_scope"
                    ):
                        reasons["dedup_scope_conflict"] += 1
                        continue
                    if index not in images[image_id].source_indices:
                        images[image_id].source_indices.append(index)
                    continue
                if len(images) >= 3:
                    reasons["image_limit"] += 1
                    continue
                examined += 1
                if examined > 30:
                    reasons["candidate_budget"] += 1
                    return Resolution(list(images.values()), dict(reasons))
                blob, reason = self.read_blob(image_id)
                if blob is None:
                    reasons[reason] += 1
                    continue
                source_url = http_url(p.get("url"))
                if source_url is None:
                    reasons["invalid_source_url"] += 1
                    continue
                meta = self._metadata(row["source_id"], row["revision_id"], image_id)
                images[image_id] = ChatImage(
                    id=image_id,
                    url=f"/api/v1/images/{image_id}",
                    caption=plain(row.get("caption")),
                    alt=plain(row.get("alt")),
                    source_url=source_url,
                    source_indices=[index],
                    attribution=meta.get("attribution"),
                    license=plain(row.get("license")) or meta.get("license"),
                    license_status=row.get("license_status") or None,
                    file_page_url=http_url(row.get("description_url")),
                    game_scope=p.get("game_scope"),
                    release_scope=p.get("release_scope"),
                )
        return Resolution(list(images.values()), dict(reasons))
