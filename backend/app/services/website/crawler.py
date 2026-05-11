from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from fastapi import HTTPException

from app.core.config import get_settings
from app.services.website.html_parser import ExtractedWebPage, extract_clean_web_content
from app.services.website.url_validator import UrlValidationService

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class HttpResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    body: bytes


@dataclass
class CrawlRequest:
    url: str
    domain_root: str | None = None
    max_depth: int = 0
    max_pages: int = 10


@dataclass
class CrawledWebsite:
    start_url: str
    domain_root: str
    pages: list[ExtractedWebPage]
    visited_urls: list[str]
    blocked_urls: list[str]


class CrawlError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class UrlFetcher:
    def fetch(self, url: str) -> HttpResponse:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": settings.website_crawler_user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.website_crawler_timeout_seconds) as response:
                return HttpResponse(
                    url=response.geturl(),
                    status_code=response.status,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            return HttpResponse(
                url=url,
                status_code=exc.code,
                headers={key.lower(): value for key, value in exc.headers.items()},
                body=exc.read(),
            )
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            error_reason = "timeout" if "timed out" in str(reason).lower() else "connection_error"
            raise CrawlError(error_reason, f"Failed to fetch URL: {reason}") from exc


class WebsiteCrawler:
    def __init__(
        self,
        validator: UrlValidationService | None = None,
        fetcher: UrlFetcher | None = None,
    ) -> None:
        self.validator = validator or UrlValidationService()
        self.fetcher = fetcher or UrlFetcher()
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request_at = 0.0
        self._request_lock = threading.Lock()

    def crawl(self, request: CrawlRequest) -> CrawledWebsite:
        normalized_start = self.validator.validate_and_normalize(request.url)
        normalized_root = self.validator.validate_and_normalize(request.domain_root or request.url)
        self.validator.assert_within_domain_root(normalized_start, normalized_root)

        queue: deque[tuple[str, int]] = deque([(normalized_start, 0)])
        visited: set[str] = set()
        enqueued: set[str] = {normalized_start}
        blocked_urls: list[str] = []
        pages: list[ExtractedWebPage] = []

        max_workers = max(1, settings.website_crawler_max_parallel_requests)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while queue and len(pages) < request.max_pages:
                current_depth = queue[0][1]
                frontier: list[str] = []
                while queue and queue[0][1] == current_depth and len(frontier) < max_workers:
                    current_url, _ = queue.popleft()
                    if current_url in visited:
                        continue
                    visited.add(current_url)
                    frontier.append(current_url)

                futures = {executor.submit(self._crawl_single_url, url): url for url in frontier}
                for future in as_completed(futures):
                    current_url = futures[future]
                    extracted, next_links, is_blocked = future.result()
                    if is_blocked:
                        blocked_urls.append(current_url)
                        continue
                    if extracted and extracted.cleaned_text and len(pages) < request.max_pages:
                        pages.append(extracted)
                        logger.info("Crawled website page", extra={"url": extracted.url, "text_size": len(extracted.cleaned_text)})
                    if current_depth >= request.max_depth:
                        continue
                    for href in next_links:
                        normalized_child = self._normalize_child_url(current_url, normalized_root, href)
                        if not normalized_child or normalized_child in visited or normalized_child in enqueued:
                            continue
                        enqueued.add(normalized_child)
                        queue.append((normalized_child, current_depth + 1))

        return CrawledWebsite(
            start_url=normalized_start,
            domain_root=normalized_root,
            pages=pages,
            visited_urls=sorted(visited),
            blocked_urls=blocked_urls,
        )

    def _normalize_child_url(self, current_url: str, normalized_root: str, href: str) -> str | None:
        href = href.strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            return None
        resolved = urllib.parse.urljoin(current_url, href)
        normalized = self.validator.validate_and_normalize(resolved)
        try:
            self.validator.assert_within_domain_root(normalized, normalized_root)
        except HTTPException:
            return None
        return normalized

    def _can_fetch(self, url: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        robots_key = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots_cache.get(robots_key)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            robots_url = urllib.parse.urljoin(f"{robots_key}/", "robots.txt")
            try:
                response = self._fetch_with_politeness(robots_url)
                if response.status_code >= 400:
                    parser.parse([])
                else:
                    parser.parse(response.body.decode("utf-8", errors="ignore").splitlines())
            except (HTTPException, CrawlError):
                parser.parse([])
            self._robots_cache[robots_key] = parser
        return parser.can_fetch(settings.website_crawler_user_agent, url)

    def _fetch_with_politeness(self, url: str) -> HttpResponse:
        with self._request_lock:
            delay = max(settings.website_crawler_request_delay_seconds, 0.0)
            elapsed = time.monotonic() - self._last_request_at
            if self._last_request_at and elapsed < delay:
                time.sleep(delay - elapsed)
            response = self.fetcher.fetch(url)
            self._last_request_at = time.monotonic()
            return response

    def _crawl_single_url(self, current_url: str) -> tuple[ExtractedWebPage | None, list[str], bool]:
        if not self._can_fetch(current_url):
            logger.warning("Blocked by robots or safety rule", extra={"url": current_url})
            return None, [], True

        response = self._fetch_with_politeness(current_url)
        if response.status_code >= 400:
            logger.warning("Website crawl returned error status", extra={"url": current_url, "status_code": response.status_code})
            return None, [], True

        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "text/plain" not in content_type:
            logger.info("Skipped unsupported content type", extra={"url": current_url, "content_type": content_type})
            return None, [], True

        html_text = response.body.decode("utf-8", errors="ignore")
        try:
            extracted = extract_clean_web_content(current_url, html_text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to parse crawled page", extra={"url": current_url})
            raise CrawlError("parsing_failed", f"Failed to parse readable content for {current_url}.") from exc

        return extracted, extracted.links, False


def synthetic_website_filename(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    base = re.sub(r"[^a-z0-9]+", "-", parsed.hostname or "website").strip("-")
    path = re.sub(r"[^a-z0-9]+", "-", parsed.path or "root").strip("-")
    return f"{base}-{path or 'root'}.txt"


def combined_checksum(texts: list[str]) -> str:
    digest = hashlib.sha256()
    for text in texts:
        digest.update(text.encode("utf-8"))
    return digest.hexdigest()
