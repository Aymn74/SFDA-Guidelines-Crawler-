from __future__ import annotations

import logging
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .config import BASE_URL, Settings, listing_url
from .parser import DocumentRecord, extract_document_links, find_pdf_links
from .pdf_utils import extract_pdf_text, safe_filename, sha256_bytes
from .storage import dedupe_records

logger = logging.getLogger(__name__)


@dataclass
class SimpleResponse:
    url: str
    content: bytes
    status_code: int = 200

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="ignore")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=None, response=None)


class PoliteHttpClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._last_request = 0.0
        self._robots = RobotFileParser()
        self._robots.set_url(f"{BASE_URL}/robots.txt")
        self._robots_available = False
        self.client = httpx.Client(
            headers=self._headers(),
            timeout=settings.timeout,
            follow_redirects=True,
        )
        try:
            self._robots.read()
            self._robots_available = True
            logger.info("Loaded robots.txt from %s", f"{BASE_URL}/robots.txt")
        except Exception as exc:
            logger.warning("Could not read robots.txt, defaulting to cautious allow for target host: %s", exc)

    def close(self) -> None:
        self.client.close()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": f"Mozilla/5.0 (compatible; {self.settings.user_agent})",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "close",
        }

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != urlparse(BASE_URL).netloc:
            return False
        if not self._robots_available:
            return True
        try:
            return self._robots.can_fetch(self.settings.user_agent, url)
        except Exception:
            return True

    def get(self, url: str) -> httpx.Response:
        if not self.can_fetch(url):
            raise PermissionError(f"robots.txt disallows fetching {url}")
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.settings.request_delay:
            time.sleep(self.settings.request_delay - elapsed)
        last_exc: Exception | None = None
        for attempt in range(1, self.settings.retries + 1):
            try:
                logger.info("GET %s (attempt %s/%s)", url, attempt, self.settings.retries)
                response = self.client.get(url)
                self._last_request = time.monotonic()
                response.raise_for_status()
                return response
            except Exception as exc:
                last_exc = exc
                try:
                    response = self._urllib_get(url)
                    self._last_request = time.monotonic()
                    return response
                except Exception as fallback_exc:
                    last_exc = fallback_exc
                sleep_for = self.settings.backoff_factor ** attempt
                logger.warning("Request failed for %s: %s; retrying in %.1fs", url, last_exc, sleep_for)
                time.sleep(sleep_for)
        raise RuntimeError(f"Failed to fetch {url}") from last_exc

    def _urllib_get(self, url: str) -> SimpleResponse:
        logger.info("Fallback urllib GET %s", url)
        request = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=self.settings.timeout) as response:
            status = getattr(response, "status", 200)
            return SimpleResponse(url=url, content=response.read(), status_code=status)


class SFDACrawler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.http = PoliteHttpClient(settings)
        self.seen_pages: set[str] = set()
        self.seen_pdfs: set[str] = set()

    def close(self) -> None:
        self.http.close()

    def crawl(self, sector: str = "Drugs", max_pages: int = 5, download_pdfs: bool = True, extract_text: bool = True) -> list[DocumentRecord]:
        records: list[DocumentRecord] = []
        for document_type in ("Guide", "Regulation"):
            for page in range(max_pages):
                url = listing_url(document_type, sector, page)
                try:
                    html = self.http.get(url).text
                except Exception as exc:
                    logger.error("Skipping listing page %s: %s", url, exc)
                    break
                page_records = extract_document_links(html, url, sector, document_type)
                logger.info("Extracted %s records from %s", len(page_records), url)
                if not page_records and page > 0:
                    break
                records.extend(self._hydrate_records(page_records, download_pdfs, extract_text))
        return dedupe_records(records)

    def _hydrate_records(self, records: Iterable[DocumentRecord], download_pdfs: bool, extract_text: bool) -> list[DocumentRecord]:
        hydrated: list[DocumentRecord] = []
        for record in records:
            if record.page_url in self.seen_pages:
                continue
            self.seen_pages.add(record.page_url)
            if not record.pdf_url or "#" not in record.page_url:
                try:
                    page_html = self.http.get(record.page_url).text
                    pdfs = find_pdf_links(page_html, record.page_url)
                    if pdfs and not record.pdf_url:
                        record.pdf_url = pdfs[0]
                except Exception as exc:
                    logger.warning("Could not inspect detail page %s: %s", record.page_url, exc)
            if download_pdfs and record.pdf_url:
                self._download_pdf(record, extract_text)
            hydrated.append(record)
        return hydrated

    def _download_pdf(self, record: DocumentRecord, extract_text_flag: bool) -> None:
        if record.pdf_url in self.seen_pdfs:
            logger.info("Skipping duplicate PDF %s", record.pdf_url)
            return
        self.seen_pdfs.add(record.pdf_url)
        raw_dir = self.settings.output_dir / "raw_pdfs"
        text_dir = self.settings.output_dir / "extracted_text"
        raw_dir.mkdir(parents=True, exist_ok=True)
        filename = safe_filename(record.title, ".pdf")
        path = raw_dir / filename
        if path.exists():
            content = path.read_bytes()
            record.pdf_file = str(path)
            record.pdf_sha256 = sha256_bytes(content)
            logger.info("Reusing existing PDF %s", path)
            if extract_text_flag:
                text_path = text_dir / f"{path.stem}.txt"
                if not text_path.exists():
                    text_path = extract_pdf_text(path, text_dir)
                record.text_file = str(text_path)
            return
        try:
            content = self.http.get(record.pdf_url).content
        except Exception as exc:
            logger.warning("PDF download failed for %s: %s", record.pdf_url, exc)
            return
        if path.exists() and sha256_bytes(path.read_bytes()) != sha256_bytes(content):
            filename = safe_filename(f"{record.title}-{sha256_bytes(content)[:10]}", ".pdf")
            path = raw_dir / filename
        path.write_bytes(content)
        record.pdf_file = str(path)
        record.pdf_sha256 = sha256_bytes(content)
        logger.info("Saved PDF %s", path)
        if extract_text_flag:
            text_path = extract_pdf_text(path, text_dir)
            record.text_file = str(text_path)
