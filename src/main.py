from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import Settings
from .crawler import SFDACrawler
from .storage import write_records


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "y"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl SFDA drug-related guidelines and regulations.")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum listing pages per source.")
    parser.add_argument("--sector", default="Drugs", help="Sector name or SFDA tag id. Default: Drugs.")
    parser.add_argument("--download-pdfs", type=parse_bool, default=True, help="Download linked PDFs.")
    parser.add_argument("--extract-text", type=parse_bool, default=True, help="Extract text from downloaded PDFs.")
    parser.add_argument("--output", type=Path, default=Path("data"), help="Output directory.")
    parser.add_argument("--request-delay", type=float, default=None, help="Delay between requests in seconds.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    settings_kwargs = {"output_dir": args.output}
    if args.request_delay is not None:
        settings_kwargs["request_delay"] = args.request_delay
    settings = Settings(**settings_kwargs)
    crawler = SFDACrawler(settings)
    try:
        records = crawler.crawl(
            sector=args.sector,
            max_pages=args.max_pages,
            download_pdfs=args.download_pdfs,
            extract_text=args.extract_text,
        )
    finally:
        crawler.close()
    csv_path, jsonl_path = write_records(records, args.output)
    logging.info("Wrote %s records to %s and %s", len(records), csv_path, jsonl_path)
    for record in records[:10]:
        print(f"{record.title} | {record.document_type} | {record.publication_date} | {record.page_url} | {record.pdf_url}")


if __name__ == "__main__":
    main()
