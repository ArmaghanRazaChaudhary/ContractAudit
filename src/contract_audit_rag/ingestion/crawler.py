from __future__ import annotations

import hashlib
import logging
import time
import urllib.robotparser
from collections import deque
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from contract_audit_rag.config import Settings, SourcePolicy
from contract_audit_rag.manifest import Manifest
from contract_audit_rag.models import DocumentRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CrawlTarget:
    url: str
    depth: int


def canonicalize_url(url: str) -> str:
    clean, _ = urldefrag(url)
    parsed = urlparse(clean)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = host if not port else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def url_allowed(url: str, policy: SourcePolicy) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and (parsed.hostname or "").lower() in policy.allowed_domains
        and any(parsed.path.startswith(prefix) for prefix in policy.allowed_path_prefixes)
    )


class GovernedCrawler:
    def __init__(self, settings: Settings, manifest: Manifest) -> None:
        self.settings = settings
        self.manifest = manifest
        self.client = httpx.Client(
            follow_redirects=True,
            timeout=settings.request_timeout,
            headers={"User-Agent": settings.user_agent},
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request: dict[str, float] = {}

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> GovernedCrawler:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _robot_parser(self, url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        robots_url = f"{origin}/robots.txt"
        parser = urllib.robotparser.RobotFileParser(robots_url)
        try:
            response = self.client.get(robots_url)
            parser.parse(response.text.splitlines() if response.is_success else [])
        except httpx.HTTPError:
            logger.warning("Could not fetch robots.txt for %s; denying crawl", origin)
            parser.parse(["User-agent: *", "Disallow: /"])
        self._robots[origin] = parser
        return parser

    def _throttle(self, host: str, delay: float) -> None:
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def _fetch(self, url: str, policy: SourcePolicy) -> httpx.Response:
        host = urlparse(url).netloc
        self._throttle(host, policy.crawl_delay_seconds)
        response = self.client.get(url)
        self._last_request[host] = time.monotonic()
        response.raise_for_status()
        declared_size = int(response.headers.get("content-length", "0"))
        if declared_size > self.settings.max_document_bytes:
            raise ValueError(f"Document exceeds size limit: {declared_size} bytes")
        if len(response.content) > self.settings.max_document_bytes:
            raise ValueError("Downloaded document exceeds size limit")
        return response

    def crawl(self, policy: SourcePolicy, limit: int = 100) -> list[DocumentRecord]:
        if not policy.storage_approved:
            raise ValueError(
                f"Source {policy.id} is not approved for local storage; review its terms "
                "and set storage_approved: true explicitly"
            )
        queue = deque(CrawlTarget(canonicalize_url(str(url)), 0) for url in policy.seeds)
        seen: set[str] = set()
        records: list[DocumentRecord] = []
        while queue and len(records) < limit:
            target = queue.popleft()
            if target.url in seen or not url_allowed(target.url, policy):
                continue
            seen.add(target.url)
            if not self._robot_parser(target.url).can_fetch(self.settings.user_agent, target.url):
                logger.warning("robots.txt denied %s", target.url)
                continue
            try:
                response = self._fetch(target.url, policy)
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if content_type not in policy.content_types:
                    continue
                record = self._store(response, target.url, policy, content_type)
                self.manifest.upsert(record)
                records.append(record)
                if content_type == "text/html" and target.depth < policy.max_depth:
                    queue.extend(
                        CrawlTarget(link, target.depth + 1)
                        for link in self._links(response.text, target.url, policy)
                        if link not in seen
                    )
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Skipping %s: %s", target.url, exc)
        return records

    def _store(
        self,
        response: httpx.Response,
        url: str,
        policy: SourcePolicy,
        content_type: str,
    ) -> DocumentRecord:
        digest = hashlib.sha256(response.content).hexdigest()
        document_id = hashlib.sha256(url.encode()).hexdigest()[:24]
        suffix = ".pdf" if content_type == "application/pdf" else ".html"
        directory = self.settings.raw_dir / policy.id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{document_id}{suffix}"
        path.write_bytes(response.content)
        title = None
        if content_type == "text/html":
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else None
        return DocumentRecord(
            document_id=document_id,
            source_id=policy.id,
            publisher=policy.publisher,
            canonical_url=url,
            content_hash=digest,
            content_type=content_type,
            license=policy.license,
            local_path=str(path),
            title=title,
        )

    @staticmethod
    def _links(html: str, base_url: str, policy: SourcePolicy) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: set[str] = set()
        for anchor in soup.select("a[href]"):
            href = anchor.get("href")
            if isinstance(href, str):
                links.add(canonicalize_url(urljoin(base_url, href)))
        return sorted(url for url in links if url_allowed(url, policy))
