from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    document_id: str
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    content_sha256: str

    @property
    def token_count_estimate(self) -> int:
        return max(1, len(self.content) // 4)


def stable_document_id(title: str, page_url: str, pdf_url: str) -> str:
    canonical = f"{page_url.strip()}|{pdf_url.strip()}" or title.strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, document_id: str, max_chars: int = 2200, overlap_chars: int = 250) -> list[TextChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be greater than or equal to 0 and less than max_chars")

    text = normalize_text(text)
    if not text:
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    while start < len(text):
        hard_end = min(start + max_chars, len(text))
        end = _best_boundary(text, start, hard_end) if hard_end < len(text) else hard_end
        content = text[start:end].strip()
        if content:
            chunks.append(
                TextChunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=content,
                    char_start=start,
                    char_end=end,
                    content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )
            index += 1
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks


def _best_boundary(text: str, start: int, hard_end: int) -> int:
    window = text[start:hard_end]
    for separator in ("\n\n", "\n", ". ", "; ", ", "):
        idx = window.rfind(separator)
        if idx >= max(80, len(window) // 2):
            return start + idx + len(separator)
    return hard_end
