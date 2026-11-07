"""Bounded async Search -> Extract. No SDK, no direct arbitrary-URL fetches."""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.rag.web_content import clean_markdown, select_excerpts
from core.types import Hit


@dataclass(frozen=True)
class WebHit(Hit):
    """Internal origin type; artifact payload cannot grant itself web admission."""


class WebSearchError(RuntimeError):
    def __init__(self, reason):
        super().__init__("Web search unavailable")
        self.reason = reason


def allowed_url(url, domains):
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.hostname not in domains
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
        ):
            return None
        return urlunsplit(("https", parts.hostname, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


class TavilySearch:
    def __init__(self, settings, *, client=None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=settings.web_search_timeout_seconds, follow_redirects=False, trust_env=False
        )
        self.owns_client = client is None

    async def aclose(self):
        if self.owns_client:
            await self.client.aclose()

    async def _post(self, endpoint, payload):
        key = self.settings.tavily_api_key
        if not key or not key.get_secret_value().strip():
            raise WebSearchError("missing_key")
        try:
            async with self.client.stream(
                "POST",
                f"https://api.tavily.com/{endpoint}",
                headers={"Authorization": f"Bearer {key.get_secret_value()}"},
                json=payload,
            ) as response:
                if response.status_code != 200:
                    reason = {401: "auth", 403: "auth", 429: "rate_limit"}.get(response.status_code, "provider")
                    raise WebSearchError(reason)
                body = bytearray()
                async for part in response.aiter_bytes():
                    body.extend(part)
                    if len(body) > 1000000:
                        raise WebSearchError("response_too_large")
            import json

            data = json.loads(body)
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise WebSearchError("schema")
            return data
        except httpx.TimeoutException:
            raise WebSearchError("timeout") from None
        except (httpx.HTTPError, ValueError):
            raise WebSearchError("provider_or_schema") from None

    async def search(self, query):
        diagnostics = {"selected_urls": 0, "failed_extracts": 0, "excluded": 0}
        try:
            async with asyncio.timeout(self.settings.web_search_timeout_seconds):
                data = await self._post(
                    "search",
                    {
                        "query": query[:2000],
                        "topic": "general",
                        "search_depth": "basic",
                        "max_results": self.settings.web_search_max_results,
                        "include_domains": self.settings.web_search_domains,
                        "include_answer": False,
                        "include_raw_content": False,
                        "include_images": True,
                        "include_image_descriptions": True,
                    },
                )
                selected = {}
                page_images = {}
                for item in data["results"][: self.settings.web_search_max_results]:
                    if not isinstance(item, dict):
                        raise WebSearchError("schema")
                    url = allowed_url(item.get("url"), self.settings.web_search_domains)
                    title = item.get("title")
                    if url and isinstance(title, str) and title.strip():
                        selected.setdefault(url, title[:300])
                        page_images[url] = (
                            [
                                im
                                for im in item.get("images", [])[:8]
                                if isinstance(im, dict) and isinstance(im.get("url"), str)
                            ]
                            if isinstance(item.get("images"), list)
                            else []
                        )
                    else:
                        diagnostics["excluded"] += 1
                diagnostics["selected_urls"] = len(selected)
                if not selected:
                    return [], diagnostics
                extracted = await self._post(
                    "extract",
                    {
                        "urls": list(selected),
                        "query": query[:2000],
                        "chunks_per_source": 3,
                        "extract_depth": "basic",
                        "format": "markdown",
                        "include_images": False,
                    },
                )
                failures = extracted.get("failed_results", [])
                if not isinstance(failures, list):
                    raise WebSearchError("schema")
                diagnostics["failed_extracts"] = len(failures)
                hits, seen = [], set()
                for item in extracted["results"][: self.settings.web_search_max_results]:
                    if not isinstance(item, dict):
                        raise WebSearchError("schema")
                    url = allowed_url(item.get("url"), self.settings.web_search_domains)
                    text = item.get("raw_content")
                    if url not in selected or not isinstance(text, str) or not text.strip() or len(text) > 60000:
                        diagnostics["excluded"] += 1
                        continue
                    text, cleanup = clean_markdown(text)
                    for key, value in cleanup.items():
                        diagnostics[key] = diagnostics.get(key, 0) + value
                    blocks, oversized = select_excerpts(text, query)
                    diagnostics["excluded"] += oversized
                    for ordinal, block in enumerate(blocks[:3]):
                        digest = hashlib.sha256((url + "\n" + block).encode()).hexdigest()
                        if not block or digest in seen:
                            continue
                        seen.add(digest)
                        hits.append(
                            WebHit(
                                "web:" + digest,
                                0.0,
                                {
                                    "text": block,
                                    "title": selected[url],
                                    "url": url,
                                    "section": f"Web excerpt {ordinal + 1}",
                                    "origin": "web",
                                    "retrieved_at": datetime.now(UTC).isoformat(),
                                    "source": "tavily_extract",
                                    "source_type": "unclassified_web",
                                    "source_type_evidence": "web_extraction_not_content_review",
                                    "content_processing": "markdown-clean-excerpts-v1",
                                    "game_scope": "unknown",
                                    "release_scope": "unknown",
                                    "patch_version": "unknown",
                                    "lang": "unknown",
                                    "review_status": "unreviewed",
                                    "image_ids": [],
                                    "web_images": page_images.get(url, []),
                                },
                            )
                        )
                if not hits and failures:
                    raise WebSearchError("extract_failed")
                return hits, diagnostics
        except TimeoutError:
            raise WebSearchError("timeout") from None
