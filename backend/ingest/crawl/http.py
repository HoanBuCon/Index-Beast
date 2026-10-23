"""Bounded HTTP with global pacing, robots, redirects and retries."""

import time
from collections import Counter
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from ingest.settings import user_agent


class CrawlError(RuntimeError):
    pass


class HttpClient:
    def __init__(self, config, *, transport=None, sleep=time.sleep, clock=time.monotonic):
        self.config = config
        self.agent = user_agent(config)
        self.allowed_hosts = set(config["crawl"]["allowed_hosts"])
        self.client = httpx.Client(
            headers={"User-Agent": self.agent, "Accept-Encoding": "identity"},
            timeout=config["crawl"]["timeout_seconds"],
            follow_redirects=False,
            transport=transport,
        )
        self.sleep, self.clock = sleep, clock
        self.last = None
        self.robots = {}
        self.stats = Counter()

    def close(self):
        self.client.close()

    def check_url(self, url):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.allowed_hosts
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise CrawlError("URL outside configured HTTPS source hosts")

    def _request(self, url, max_bytes, interval):
        retries = self.config["crawl"]["max_retries"]
        for attempt in range(retries + 1):
            if self.last is not None:
                self.sleep(max(0, interval - (self.clock() - self.last)))
            self.last = self.clock()
            self.stats["requests"] += 1
            try:
                with self.client.stream("GET", url) as response:
                    body = bytearray()
                    for part in response.iter_bytes():
                        body.extend(part)
                        if len(body) > max_bytes:
                            raise CrawlError("Response exceeds byte limit")
                    result = httpx.Response(
                        response.status_code, headers=response.headers, content=bytes(body), request=response.request
                    )
                if result.status_code not in (429, 500, 502, 503, 504):
                    return result
                reason = f"HTTP {result.status_code}"
                try:
                    pause = float(result.headers.get("Retry-After", ""))
                except ValueError:
                    try:
                        pause = (
                            parsedate_to_datetime(result.headers.get("Retry-After", "")) - datetime.now(UTC)
                        ).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        pause = 2 ** (attempt + 1)
            except httpx.TransportError as exc:
                reason, pause = type(exc).__name__, 2 ** (attempt + 1)
            if attempt == retries or pause > 60:
                raise CrawlError(f"{reason}; retry budget/wait limit reached")
            self.stats["retries"] += 1
            self.sleep(max(0, pause))
        raise CrawlError("Retry budget exhausted")

    def policy(self, url):
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            robots_url = origin + "/robots.txt"
            for _ in range(5):
                response = self._request(robots_url, 1_000_000, self.config["crawl"]["min_interval_seconds"])
                if response.is_redirect:
                    robots_url = urljoin(robots_url, response.headers.get("Location", ""))
                    self.check_url(robots_url)
                    if urlsplit(robots_url).netloc != parsed.netloc:
                        raise CrawlError("Cross-host robots redirect")
                    continue
                if response.status_code not in (200, 404):
                    raise CrawlError(f"Cannot verify robots: HTTP {response.status_code}")
                if response.status_code == 200 and "<html" in response.text[:500].lower():
                    raise CrawlError("robots response is HTML")
                robot = RobotFileParser()
                robot.parse(response.text.splitlines() if response.status_code == 200 else [])
                self.robots[origin] = robot
                break
            else:
                raise CrawlError("robots redirect loop")
        robot = self.robots[origin]
        if not robot.can_fetch(self.agent, url):
            raise CrawlError("robots.txt disallows request")
        delay = max(self.config["crawl"]["min_interval_seconds"], robot.crawl_delay(self.agent) or 0)
        if delay > 60:
            raise CrawlError("robots crawl-delay exceeds 60 seconds")
        return delay

    def get(self, url, *, max_bytes=8_000_000):
        for _ in range(6):
            self.check_url(url)
            response = self._request(url, max_bytes, self.policy(url))
            if response.is_redirect:
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            if response.status_code != 200:
                raise CrawlError(f"HTTP {response.status_code}")
            return response
        raise CrawlError("Too many redirects")

    def json(self, url):
        response = self.get(url)
        try:
            result = response.json()
        except ValueError as exc:
            raise CrawlError("Expected JSON; possible challenge or changed endpoint") from exc
        if not isinstance(result, dict):
            raise CrawlError("Expected JSON object")
        return result
