from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from pathlib import Path

logger = logging.getLogger(__name__)


def safe_filename(title: str, extension: str = "") -> str:
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)[:120] or "document"
    ext = extension if extension.startswith(".") or not extension else f".{extension}"
    return f"{slug}{ext.lower()}"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extract_pdf_text(pdf_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    text_path = output_dir / f"{pdf_path.stem}.txt"
    text = ""
    try:
        import fitz

        with fitz.open(pdf_path) as doc:
            text = "\n\n".join(page.get_text("text") for page in doc)
    except Exception as fitz_error:
        logger.warning("PyMuPDF extraction failed for %s: %s; trying pypdf", pdf_path, fitz_error)
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf_path))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as pypdf_error:
            logger.error("PDF text extraction failed for %s: %s", pdf_path, pypdf_error)
            text = ""
    text_path.write_text(text, encoding="utf-8")
    return text_path
