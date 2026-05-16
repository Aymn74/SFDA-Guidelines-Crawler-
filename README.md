# SFDA Guidelines Crawler

MVP crawler for drug-related SFDA guidelines, regulations, and linked PDF documents from the official Saudi Food & Drug Authority website.

## What It Collects

- Title
- Sector/category
- Document type
- Publication/update date when visible
- Page URL
- PDF URL when available
- Language
- Source listing page
- Crawl timestamp
- Downloaded PDF path
- PDF SHA-256 checksum
- Extracted text path

The crawler starts with:

- `https://www.sfda.gov.sa/en/Guide?tags=2`
- `https://www.sfda.gov.sa/en/regulations?tags=2`

Note: the SFDA navigation currently maps the Drugs sector to `tags=2`. `tags=1` appears in the site navigation as Food.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Optionally copy `.env.example` to `.env` and adjust polite crawling settings. The current CLI reads environment variables directly.

## Run

```bash
python -m src.main --sector Drugs --download-pdfs true --extract-text true --max-pages 5
```

For a very small metadata-only smoke test:

```bash
python -m src.main --sector Drugs --download-pdfs false --extract-text false --max-pages 1 --request-delay 2
```

Outputs are written to:

- `data/raw_pdfs/`
- `data/extracted_text/`
- `data/sfda_guidelines.csv`
- `data/sfda_guidelines.jsonl`

## Tests

```bash
python -m pytest
```

## Politeness and Robustness

- Reads `robots.txt` before crawling.
- Uses a configurable user agent.
- Adds request delay between requests.
- Retries with exponential backoff.
- Applies request timeouts.
- Deduplicates page URLs and PDF URLs.
- Uses safe normalized filenames.

## Limitations

- This MVP uses static HTML parsing with `httpx` and BeautifulSoup. If SFDA moves listing data fully behind JavaScript, add Playwright as a fallback fetcher.
- Metadata quality depends on what each listing/detail page exposes consistently.
- PDF text extraction can vary for scanned PDFs; OCR is not included.

## Next Step: Embeddings and Supabase pgvector

1. Split extracted text files into chunks with source metadata.
2. Generate embeddings for each chunk.
3. Store document metadata in a `sfda_documents` table.
4. Store chunks and vectors in a `sfda_document_chunks` table with `pgvector`.
5. Add hybrid search over title, metadata filters, and vector similarity.
