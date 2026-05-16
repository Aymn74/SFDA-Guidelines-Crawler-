from src.chunking import chunk_text, stable_document_id


def test_chunk_text_preserves_metadata_and_overlap():
    text = "A" * 120 + "\n\n" + "B" * 120 + "\n\n" + "C" * 120

    chunks = chunk_text(text, document_id="doc-1", max_chars=180, overlap_chars=20)

    assert len(chunks) == 3
    assert chunks[0].document_id == "doc-1"
    assert chunks[0].chunk_index == 0
    assert chunks[1].char_start < chunks[0].char_end
    assert all(chunk.content for chunk in chunks)
    assert all(chunk.content_sha256 for chunk in chunks)


def test_stable_document_id_uses_canonical_source_fields():
    first = stable_document_id("Title", "https://example.com/page", "https://example.com/a.pdf")
    second = stable_document_id("Different", "https://example.com/page", "https://example.com/a.pdf")

    assert first == second
