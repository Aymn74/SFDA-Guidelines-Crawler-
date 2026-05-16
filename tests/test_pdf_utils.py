from src.pdf_utils import sha256_bytes, safe_filename


def test_safe_filename_normalizes_title_and_extension():
    assert safe_filename("SFDA GMP Guide: Version 3/2024", ".pdf") == "sfda-gmp-guide-version-3-2024.pdf"


def test_sha256_bytes_returns_stable_digest():
    assert sha256_bytes(b"sfda") == "d23da8b335edf8c13bc136f4ef4a5f97e2645c0c10833894974b2103ebfa1b18"
