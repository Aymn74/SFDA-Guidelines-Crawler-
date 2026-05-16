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

## Embeddings and Supabase pgvector

Apply the schema in `supabase/migrations/202605160001_sfda_pgvector.sql` to your Supabase project. The migration creates:

- `sfda_documents`
- `sfda_document_chunks`
- `match_sfda_guidelines(...)` hybrid search RPC

The vector column is `extensions.vector(1536)` for `text-embedding-3-small`. If you change `OPENAI_EMBEDDING_DIMENSIONS`, update the migration to the same dimension before ingesting.

Configure secrets in `.env`:

```bash
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
```

Preview chunk counts without API calls:

```bash
python -m src.embedding_pipeline --metadata data/sfda_guidelines.csv --dry-run
```

Generate embeddings and upsert documents/chunks:

```bash
python -m src.embedding_pipeline --metadata data/sfda_guidelines.csv --batch-size 16
```

Hybrid search:

```bash
python -m src.search "clinical trial drug submission requirements" --sector Drugs --match-count 5
```

Use the Supabase service role key only in trusted server-side environments. Do not expose it in browser or client-side apps.

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

## Next Step: Production Hardening

1. Add a scheduled crawl job.
2. Add OCR fallback for scanned PDFs.
3. Add CI that runs tests on every push.
4. Add a small API around `match_sfda_guidelines` for applications.
