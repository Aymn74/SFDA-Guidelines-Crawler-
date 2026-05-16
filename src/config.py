from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_URL = "https://www.sfda.gov.sa"
START_URLS = {
    "Guide": f"{BASE_URL}/en/Guide",
    "Regulation": f"{BASE_URL}/en/regulations",
}
SECTOR_TAGS = {
    "Food": "1",
    "Drugs": "2",
    "Medical Devices": "3",
}


@dataclass(frozen=True)
class Settings:
    user_agent: str = os.getenv("SFDA_USER_AGENT", "sfda-guidelines-crawler/0.1 (+research; polite)")
    request_delay: float = float(os.getenv("SFDA_REQUEST_DELAY", "2.0"))
    timeout: float = float(os.getenv("SFDA_TIMEOUT", "30"))
    retries: int = int(os.getenv("SFDA_RETRIES", "3"))
    backoff_factor: float = float(os.getenv("SFDA_BACKOFF_FACTOR", "1.5"))
    output_dir: Path = Path(os.getenv("SFDA_OUTPUT_DIR", "data"))


def listing_url(document_type: str, sector: str, page: int = 0) -> str:
    tag = SECTOR_TAGS.get(sector, sector)
    base = START_URLS[document_type]
    sep = "&" if "?" in base else "?"
    page_param = f"&page={page}" if page else ""
    return f"{base}{sep}tags={tag}{page_param}"
