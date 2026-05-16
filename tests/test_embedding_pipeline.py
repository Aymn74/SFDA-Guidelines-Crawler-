from pathlib import Path

from src.chunking import TextChunk
from src.embedding_pipeline import build_chunk_payload, load_documents_from_metadata


def test_load_documents_from_metadata_reads_text_file(tmp_path):
    text_file = tmp_path / "doc.txt"
    text_file.write_text("Clinical trial guideline text", encoding="utf-8")
    metadata = tmp_path / "sfda_guidelines.csv"
    metadata.write_text(
        "title,sector,document_type,publication_date,page_url,pdf_url,language,source_page,crawl_timestamp,pdf_file,pdf_sha256,text_file\n"
        f"Title,Drugs,Guide,2026-01-01,https://x/page,https://x/doc.pdf,en,https://x/list,now,,abc,{text_file}\n",
        encoding="utf-8",
    )

    documents = load_documents_from_metadata(metadata)

    assert documents[0].title == "Title"
    assert documents[0].text == "Clinical trial guideline text"
    assert documents[0].document_id


def test_build_chunk_payload_includes_embedding_and_metadata():
    chunk = TextChunk(
        document_id="doc-1",
        chunk_index=2,
        content="Good manufacturing practice",
        char_start=10,
        char_end=37,
        content_sha256="hash",
    )

    payload = build_chunk_payload(chunk, embedding=[0.1, 0.2], model="test-model", dimensions=2)

    assert payload["document_id"] == "doc-1"
    assert payload["embedding"] == [0.1, 0.2]
    assert payload["embedding_model"] == "test-model"
    assert payload["embedding_dimensions"] == 2
