"""Image occurrences keep page/section provenance; blobs are content-addressed."""

import io
import warnings
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

from ingest.artifacts import now, read, save, sha256, write_bytes
from ingest.crawl.http import CrawlError

UI = {"navbox", "toc", "mw-editsection", "er-icon", "mw-cite-backlink", "wds-global-navigation"}


def image_occurrences(raw):
    soup = BeautifulSoup(raw["content"], "html.parser")
    body = soup.select_one(".mw-parser-output, #page-content, main") or soup
    headings, result = [], []
    for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "img"]):
        if any(set(parent.get("class", [])) & UI for parent in [element, *element.parents] if parent.name):
            continue
        infobox = element.find_parent(class_="portable-infobox")
        if element.name.startswith("h") and infobox:
            continue
        if element.name.startswith("h"):
            level = int(element.name[1])
            headings = [(n, t) for n, t in headings if n < level]
            headings.append((level, element.get_text(" ", strip=True)))
            continue
        src = element.get("src") or element.get("data-src")
        if not src:
            continue
        parent = element.find_parent("a")
        href = urljoin(raw["url"], parent.get("href", "")) if parent else ""
        title = unquote(urlsplit(href).path.rsplit("/", 1)[-1]).replace("_", " ")
        if not title.startswith("File:"):
            title = None
        container = element.find_parent(class_=["gallerybox", "thumb", "pi-image", "pi-item"]) or element.find_parent(
            "figure"
        )
        caption = container.select_one(".gallerytext, .thumbcaption, .pi-caption, figcaption") if container else None
        width, height = element.get("width"), element.get("height")
        small = bool(
            width and height and str(width).isdigit() and str(height).isdigit() and max(int(width), int(height)) <= 40
        )
        interface_rating = "menu_icon_message_rating" in unquote(src).lower()
        small = small or interface_rating
        result.append(
            {
                "occurrence_id": len(result),
                "section": "Infobox" if infobox else (" > ".join(t for _, t in headings) or "Introduction"),
                "alt": element.get("alt", ""),
                "caption": caption.get_text(" ", strip=True) if caption else "",
                "file_title": title,
                "description_url": href if title else None,
                "display_url": urljoin(raw["url"], src),
                "status": "excluded" if small else "pending",
                "reason": "interface_rating_icon" if interface_rating else ("small_interface_icon" if small else None),
                "scope_status": "requires_section_review",
            }
        )
    return result


def verify_image(data, mime, settings):
    if mime not in settings["allowed_mimes"]:
        raise CrawlError("Unsupported image MIME")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > settings["max_pixels"]:
                    raise CrawlError("Image exceeds pixel limit")
                detected = Image.MIME.get(image.format)
                if detected not in settings["allowed_mimes"]:
                    raise CrawlError("Decoded image format is not allowed")
                dimensions = (image.width, image.height)
                image.verify()
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise CrawlError("Invalid or unsafe image file") from exc
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}[detected]
    return extension, dimensions


class MediaStore:
    def __init__(self, client, config, *, manifest_root=None):
        self.client, self.config = client, config
        self.root = config["data_dir"]
        self.manifest_root = manifest_root or self.root / "media" / "manifests"
        self.index_path = self.root / "media" / "url-index.json"
        self.index = read(self.index_path) if self.index_path.exists() else {}

    def download(self, url, source_sha1=None):
        cached = self.index.get(url)
        if cached and cached.get("source_sha1") == source_sha1:
            path = (self.root / cached["path"]).resolve()
            if (
                path.is_relative_to(self.root.resolve())
                and path.is_file()
                and sha256(path.read_bytes()) == cached["sha256"]
            ):
                return dict(cached, status="cached")
        response = self.client.get(url, max_bytes=self.config["media"]["max_bytes"])
        mime = response.headers.get("content-type", "").split(";")[0].lower()
        extension, dimensions = verify_image(response.content, mime, self.config["media"])
        digest = sha256(response.content)
        path = self.root / "media" / "blobs" / digest[:2] / (digest + extension)
        if not path.exists() or sha256(path.read_bytes()) != digest:
            write_bytes(path, response.content)
        record = {
            "image_id": digest,
            "sha256": digest,
            "source_sha1": source_sha1,
            "path": path.relative_to(self.root).as_posix(),
            "mime": {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}[extension],
            "declared_mime": mime,
            "mime_mismatch": {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}[
                mime
            ]
            != extension,
            "width": dimensions[0],
            "height": dimensions[1],
            "bytes": len(response.content),
            "fetched_at": now(),
        }
        self.index[url] = record
        save(self.index_path, self.index)
        return dict(record, status="downloaded")

    def page(self, source, raw):
        path = self.manifest_root / source.name / (raw["source_id"] + ".json")
        occurrences = image_occurrences(raw)
        manifest = {
            "source_id": raw["source_id"],
            "source": source.name,
            "page_url": raw["url"],
            "revision_id": raw["revision_id"],
            "updated_at": now(),
            "images": occurrences,
            "status": "running",
        }
        save(path, manifest)
        titles = [x["file_title"] for x in occurrences if x["file_title"] and x["status"] == "pending"]
        try:
            infos = source.image_info(titles)
            metadata_error = None
        except CrawlError as exc:
            infos, metadata_error = {}, str(exc)
        try:
            for item in occurrences:
                if item["status"] == "excluded":
                    continue
                info = infos.get(item["file_title"], {})
                metadata = info.get("extmetadata", {})
                item["extmetadata"] = metadata
                item["license"] = metadata.get("LicenseShortName", {}).get("value")
                item["license_url"] = metadata.get("LicenseUrl", {}).get("value")
                item["artist"] = metadata.get("Artist", {}).get("value")
                item["license_status"] = "reported_by_source" if item["license"] else "unknown_review_required"
                item["metadata_error"] = metadata_error
                item["description_url"] = info.get("descriptionurl") or item["description_url"]
                item["source_url"] = info.get("url") or item["display_url"]
                item["rendition"] = "original" if info.get("url") else "display_fallback"
                try:
                    item.update(self.download(item["source_url"], info.get("sha1")))
                except (CrawlError, ValueError, OSError) as exc:
                    item.update(status="failed", error=str(exc))
                save(path, manifest)
            manifest["status"] = (
                "completed_with_errors"
                if any(x["status"] == "failed" for x in occurrences) or metadata_error
                else "completed"
            )
        finally:
            save(path, manifest)
        return manifest
