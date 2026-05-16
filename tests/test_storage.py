import json

from src.parser import DocumentRecord
from src.storage import write_records


def test_write_records_deduplicates_by_page_and_pdf_url(tmp_path):
    records = [
        DocumentRecord(title="A", sector="Drugs", document_type="Guideline", page_url="https://x/a", pdf_url="https://x/a.pdf"),
        DocumentRecord(title="A duplicate", sector="Drugs", document_type="Guideline", page_url="https://x/a", pdf_url="https://x/a.pdf"),
    ]

    csv_path, jsonl_path = write_records(records, tmp_path)

    assert csv_path.exists()
    rows = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["title"] == "A"
