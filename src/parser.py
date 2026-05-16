from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .config import BASE_URL


DRUG_TERMS = {
    "drug",
    "drugs",
    "medicine",
    "medicines",
    "pharmaceutical",
    "pharmacovigilance",
    "clinical trial",
    "clinical trials",
    "gmp",
    "bioequivalence",
    "human drugs",
    "drug approvals",
    "efficacy",
    "safety of medicines",
    "good review practices",
}
SECTOR_LABELS = {
    "authority",
    "food",
    "drugs",
    "medical devices",
    "cosmetics",
    "pesticides",
    "laboratories",
    "halal",
    "nutrition",
    "food, drugs, medical devices",
}


@dataclass
class DocumentRecord:
    title: str
    sector: str = ""
    document_type: str = ""
    publication_date: str = ""
    page_url: str = ""
    pdf_url: str = ""
    language: str = "en"
    source_page: str = ""
    crawl_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pdf_file: str = ""
    pdf_sha256: str = ""
    text_file: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_date(text: str, datetime_value: str | None = None) -> str:
    candidates = [datetime_value or "", text or ""]
    formats = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d")
    for candidate in candidates:
        candidate = clean_text(candidate)
        if not candidate:
            continue
        match = re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{4}", candidate)
        if not match:
            continue
        raw = match.group(0)
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                pass
    return ""


def is_drug_related(title: str, sector: str = "", body: str = "") -> bool:
    haystack = f"{title} {sector} {body}".lower()
    explicit_non_drug_sector = re.search(r"\b(food|medical devices?|cosmetics?|pesticides?)\b", body.lower())
    title_has_drug_signal = any(term in title.lower() for term in DRUG_TERMS)
    if explicit_non_drug_sector and not title_has_drug_signal:
        return False
    if "drug" in sector.lower() or sector.strip().lower() == "drugs":
        return True
    return any(term in haystack for term in DRUG_TERMS)


def _row_candidates(soup: BeautifulSoup) -> Iterable[Tag]:
    selectors = [
        "article.warning-item",
        ".views-row",
        ".view-content > div",
        ".search-result",
        "article",
        ".card",
        ".item-list li",
    ]
    seen: set[int] = set()
    for selector in selectors:
        for node in soup.select(selector):
            ident = id(node)
            if ident not in seen and node.find("a", href=True):
                seen.add(ident)
                yield node


def _best_title_link(row: Tag) -> tuple[str, str]:
    links = row.find_all("a", href=True)
    scored: list[tuple[int, str, str]] = []
    for link in links:
        href = link.get("href", "")
        title = clean_text(link.get_text(" ", strip=True)) or clean_text(link.get("title", ""))
        if not title or href.startswith("#") or "javascript:" in href.lower():
            continue
        score = len(title)
        if ".pdf" in href.lower():
            score -= 100
        if href.startswith("/en/") or "sfda.gov.sa/en/" in href:
            score += 20
        scored.append((score, title, href))
    if not scored:
        return "", ""
    _, title, href = max(scored, key=lambda item: item[0])
    return title, urljoin(BASE_URL, href)


def _sfda_card_record(
    row: Tag,
    source_page: str,
    sector: str,
    fallback_document_type: str,
    language: str,
) -> DocumentRecord | None:
    title_node = row.select_one(".m-c-title")
    if not title_node:
        return None
    title = clean_text(title_node.get_text(" ", strip=True))
    row_text = clean_text(row.get_text(" ", strip=True))
    if not title or not is_drug_related(title, sector, row_text):
        return None
    tags = [clean_text(tag.get_text(" ", strip=True)) for tag in row.select(".custom-tags a, .cat")]
    doc_type = next((tag for tag in tags if tag and tag.lower() not in SECTOR_LABELS), fallback_document_type)
    date_node = row.select_one(".news-date")
    pdfs = find_pdf_links(str(row), source_page)
    page_url = f"{source_page}#{safe_anchor(title)}"
    return DocumentRecord(
        title=title,
        sector=sector,
        document_type=doc_type,
        publication_date=parse_date(date_node.get_text(" ", strip=True) if date_node else row_text),
        page_url=page_url,
        pdf_url=pdfs[0] if pdfs else "",
        language=language,
        source_page=source_page,
    )


def safe_anchor(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "document"


def find_pdf_links(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    pdfs: list[str] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        absolute = urljoin(page_url, href)
        if absolute not in seen:
            seen.add(absolute)
            pdfs.append(absolute)
    return pdfs


def extract_document_links(
    html: str,
    source_page: str,
    sector: str,
    document_type: str,
    language: str = "en",
) -> list[DocumentRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[DocumentRecord] = []
    seen_urls: set[str] = set()
    for row in _row_candidates(soup):
        sfda_card = _sfda_card_record(row, source_page, sector, document_type, language)
        if sfda_card:
            if sfda_card.page_url not in seen_urls:
                records.append(sfda_card)
                seen_urls.add(sfda_card.page_url)
            continue
        title, page_url = _best_title_link(row)
        if not title or page_url in seen_urls:
            continue
        row_text = clean_text(row.get_text(" ", strip=True))
        if not is_drug_related(title, sector, row_text):
            continue
        time_node = row.find("time")
        date_text = time_node.get_text(" ", strip=True) if time_node else row_text
        date_value = time_node.get("datetime") if time_node else None
        pdfs = find_pdf_links(str(row), source_page)
        records.append(
            DocumentRecord(
                title=title,
                sector=sector,
                document_type=document_type,
                publication_date=parse_date(date_text, date_value),
                page_url=page_url,
                pdf_url=pdfs[0] if pdfs else "",
                language=language,
                source_page=source_page,
            )
        )
        seen_urls.add(page_url)
    return records
