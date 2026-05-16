from pathlib import Path


def test_supabase_migration_defines_documents_chunks_and_hybrid_search():
    sql = Path("supabase/migrations/202605160001_sfda_pgvector.sql").read_text(encoding="utf-8").lower()

    assert "create extension if not exists vector" in sql
    assert "create table if not exists public.sfda_documents" in sql
    assert "create table if not exists public.sfda_document_chunks" in sql
    assert "embedding extensions.vector(1536)" in sql
    assert "match_sfda_guidelines" in sql
    assert "enable row level security" in sql
