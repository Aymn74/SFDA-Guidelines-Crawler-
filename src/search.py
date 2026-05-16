from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv
from supabase import create_client

from .embedding_pipeline import OpenAIEmbeddingProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hybrid search SFDA document chunks in Supabase pgvector.")
    parser.add_argument("query")
    parser.add_argument("--sector", default=None)
    parser.add_argument("--document-type", default=None)
    parser.add_argument("--language", default=None)
    parser.add_argument("--match-count", type=int, default=10)
    parser.add_argument("--model", default=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
    parser.add_argument("--dimensions", type=int, default=int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536")))
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    provider = OpenAIEmbeddingProvider(args.model, args.dimensions)
    query_embedding = provider.embed_texts([args.query])[0]
    supabase = create_client(supabase_url, supabase_key)
    response = supabase.rpc(
        "match_sfda_guidelines",
        {
            "query_embedding": query_embedding,
            "query_text": args.query,
            "match_count": args.match_count,
            "filter_sector": args.sector,
            "filter_document_type": args.document_type,
            "filter_language": args.language,
        },
    ).execute()
    for row in response.data:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
