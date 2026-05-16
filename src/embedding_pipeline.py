from __future__ import annotations

import argparse
import csv
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from dotenv import load_dotenv

from .chunking import TextChunk, chunk_text, stable_document_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    title: str
    sector: str
    document_type: str
    publication_date: str
    page_url: str
    pdf_url: str
    language: str
    source_page: str
    crawl_timestamp: str
    pdf_file: str
    pdf_sha256: str
    text_file: str
    text: str


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingProvider:
    def __init__(self, model: str, dimensions: int | None = None, api_key: str | None = None):
        from openai import OpenAI

        self.model = model
        self.dimensions = dimensions
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        kwargs = {"model": self.model, "input": texts}
        if self.dimensions:
            kwargs["dimensions"] = self.dimensions
        response = self.client.embeddings.create(**kwargs)
        return [item.embedding for item in response.data]


def load_documents_from_metadata(metadata_path: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    with metadata_path.open("r", encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            text_file = Path(row.get("text_file", ""))
            if not text_file.exists():
                logger.warning("Skipping %s because text file is missing: %s", row.get("title", ""), text_file)
                continue
            text = text_file.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                logger.warning("Skipping %s because extracted text is empty", row.get("title", ""))
                continue
            documents.append(
                SourceDocument(
                    document_id=stable_document_id(row.get("title", ""), row.get("page_url", ""), row.get("pdf_url", "")),
                    title=row.get("title", ""),
                    sector=row.get("sector", ""),
                    document_type=row.get("document_type", ""),
                    publication_date=row.get("publication_date", ""),
                    page_url=row.get("page_url", ""),
                    pdf_url=row.get("pdf_url", ""),
                    language=row.get("language", "en"),
                    source_page=row.get("source_page", ""),
                    crawl_timestamp=row.get("crawl_timestamp", ""),
                    pdf_file=row.get("pdf_file", ""),
                    pdf_sha256=row.get("pdf_sha256", ""),
                    text_file=str(text_file),
                    text=text,
                )
            )
    return documents


def build_document_payload(document: SourceDocument) -> dict:
    return {
        "id": document.document_id,
        "title": document.title,
        "sector": document.sector,
        "document_type": document.document_type,
        "publication_date": document.publication_date or None,
        "page_url": document.page_url,
        "pdf_url": document.pdf_url,
        "language": document.language,
        "source_page": document.source_page,
        "crawl_timestamp": document.crawl_timestamp or None,
        "pdf_file": document.pdf_file,
        "pdf_sha256": document.pdf_sha256,
        "text_file": document.text_file,
    }


def build_chunk_payload(chunk: TextChunk, embedding: list[float], model: str, dimensions: int) -> dict:
    return {
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "token_count_estimate": chunk.token_count_estimate,
        "content_sha256": chunk.content_sha256,
        "embedding": embedding,
        "embedding_model": model,
        "embedding_dimensions": dimensions,
        "metadata": {
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
        },
    }


def batched(items: list, batch_size: int) -> Iterable[list]:
    for idx in range(0, len(items), batch_size):
        yield items[idx : idx + batch_size]


def ingest_embeddings(
    metadata_path: Path,
    supabase_url: str,
    supabase_key: str,
    provider: EmbeddingProvider,
    model: str,
    dimensions: int,
    max_chars: int = 2200,
    overlap_chars: int = 250,
    batch_size: int = 32,
    dry_run: bool = False,
) -> tuple[int, int]:
    documents = load_documents_from_metadata(metadata_path)
    if dry_run:
        chunk_count = sum(len(chunk_text(doc.text, doc.document_id, max_chars, overlap_chars)) for doc in documents)
        return len(documents), chunk_count

    from supabase import create_client

    supabase = create_client(supabase_url, supabase_key)
    doc_payloads = [build_document_payload(doc) for doc in documents]
    if doc_payloads:
        supabase.table("sfda_documents").upsert(doc_payloads, on_conflict="id").execute()

    all_chunk_payloads: list[dict] = []
    for document in documents:
        chunks = chunk_text(document.text, document.document_id, max_chars, overlap_chars)
        for chunk_batch in batched(chunks, batch_size):
            embeddings = provider.embed_texts([chunk.content for chunk in chunk_batch])
            all_chunk_payloads.extend(
                build_chunk_payload(chunk, embedding, model, dimensions)
                for chunk, embedding in zip(chunk_batch, embeddings)
            )

    for payload_batch in batched(all_chunk_payloads, batch_size):
        supabase.table("sfda_document_chunks").upsert(
            payload_batch,
            on_conflict="document_id,chunk_index",
        ).execute()

    return len(documents), len(all_chunk_payloads)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Embed SFDA extracted text and store chunks in Supabase pgvector.")
    parser.add_argument("--metadata", type=Path, default=Path("data/sfda_guidelines.csv"))
    parser.add_argument("--model", default=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    parser.add_argument("--dimensions", type=int, default=int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536")))
    parser.add_argument("--max-chars", type=int, default=2200)
    parser.add_argument("--overlap-chars", type=int, default=250)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not args.dry_run and (not supabase_url or not supabase_key):
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, or run with --dry-run.")
    provider = OpenAIEmbeddingProvider(args.model, args.dimensions) if not args.dry_run else None
    documents, chunks = ingest_embeddings(
        metadata_path=args.metadata,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        provider=provider,  # type: ignore[arg-type]
        model=args.model,
        dimensions=args.dimensions,
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    print(f"documents={documents} chunks={chunks}")


if __name__ == "__main__":
    main()
