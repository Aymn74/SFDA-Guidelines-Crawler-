from __future__ import annotations

import csv
import json
from pathlib import Path

from .parser import DocumentRecord


FIELDNAMES = [
    "title",
    "sector",
    "document_type",
    "publication_date",
    "page_url",
    "pdf_url",
    "language",
    "source_page",
    "crawl_timestamp",
    "pdf_file",
    "pdf_sha256",
    "text_file",
]


def dedupe_records(records: list[DocumentRecord]) -> list[DocumentRecord]:
    unique: list[DocumentRecord] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.page_url, record.pdf_url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def write_records(records: list[DocumentRecord], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = dedupe_records(records)
    csv_path = output_dir / "sfda_guidelines.csv"
    jsonl_path = output_dir / "sfda_guidelines.jsonl"

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())

    with jsonl_path.open("w", encoding="utf-8") as jsonl_file:
        for record in records:
            jsonl_file.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    return csv_path, jsonl_path
