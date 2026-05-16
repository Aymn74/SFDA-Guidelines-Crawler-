create extension if not exists vector with schema extensions;

create table if not exists public.sfda_documents (
  id text primary key,
  title text not null,
  sector text,
  document_type text,
  publication_date date,
  page_url text not null,
  pdf_url text,
  language text default 'en',
  source_page text,
  crawl_timestamp timestamptz,
  pdf_file text,
  pdf_sha256 text,
  text_file text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (page_url, pdf_url)
);

create table if not exists public.sfda_document_chunks (
  id bigint primary key generated always as identity,
  document_id text not null references public.sfda_documents(id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  char_start integer not null,
  char_end integer not null,
  token_count_estimate integer,
  content_sha256 text not null,
  embedding_model text not null,
  embedding_dimensions integer not null default 1536,
  embedding extensions.vector(1536) not null,
  metadata jsonb not null default '{}'::jsonb,
  search_vector tsvector generated always as (to_tsvector('english', coalesce(content, ''))) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_id, chunk_index),
  unique (content_sha256, embedding_model)
);

create index if not exists sfda_documents_title_idx
  on public.sfda_documents using gin (to_tsvector('english', coalesce(title, '')));

create index if not exists sfda_documents_metadata_idx
  on public.sfda_documents (sector, document_type, language, publication_date);

create index if not exists sfda_document_chunks_search_idx
  on public.sfda_document_chunks using gin (search_vector);

create index if not exists sfda_document_chunks_embedding_hnsw_idx
  on public.sfda_document_chunks using hnsw (embedding vector_cosine_ops);

alter table public.sfda_documents enable row level security;
alter table public.sfda_document_chunks enable row level security;

create or replace function public.match_sfda_guidelines(
  query_embedding extensions.vector(1536),
  query_text text default null,
  match_count integer default 10,
  filter_sector text default null,
  filter_document_type text default null,
  filter_language text default null
)
returns table (
  chunk_id bigint,
  document_id text,
  title text,
  sector text,
  document_type text,
  publication_date date,
  page_url text,
  pdf_url text,
  language text,
  chunk_index integer,
  content text,
  similarity double precision,
  keyword_rank real,
  hybrid_score double precision
)
language sql
stable
security invoker
as $$
  with scored as (
    select
      c.id as chunk_id,
      d.id as document_id,
      d.title,
      d.sector,
      d.document_type,
      d.publication_date,
      d.page_url,
      d.pdf_url,
      d.language,
      c.chunk_index,
      c.content,
      1 - (c.embedding <=> query_embedding) as similarity,
      case
        when query_text is null or length(trim(query_text)) = 0 then 0::real
        else ts_rank_cd(
          setweight(to_tsvector('english', coalesce(d.title, '')), 'A') || c.search_vector,
          plainto_tsquery('english', query_text)
        )
      end as keyword_rank
    from public.sfda_document_chunks c
    join public.sfda_documents d on d.id = c.document_id
    where (filter_sector is null or d.sector = filter_sector)
      and (filter_document_type is null or d.document_type = filter_document_type)
      and (filter_language is null or d.language = filter_language)
  )
  select
    scored.*,
    (0.7 * similarity + 0.3 * least(keyword_rank::double precision, 1.0)) as hybrid_score
  from scored
  order by hybrid_score desc, similarity desc
  limit match_count;
$$;
