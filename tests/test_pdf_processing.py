import fitz
import pytest

from app.pdf_processing import (
    PdfProcessingError,
    build_chunks,
    extract_pages,
)


def make_pdf(*page_contents: str) -> bytes:
    document = fitz.open()
    for content in page_contents:
        page = document.new_page()
        page.insert_text((72, 72), content)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def test_extracts_text_with_one_based_page_numbers() -> None:
    pages = extract_pages(make_pdf("Primeira proposta", "Segunda proposta"))

    assert [(page.page, page.content) for page in pages] == [
        (1, "Primeira proposta"),
        (2, "Segunda proposta"),
    ]


def test_chunks_never_mix_pages() -> None:
    pages = extract_pages(make_pdf("segurança pública", "educação básica"))

    chunks = build_chunks(pages)

    assert [(chunk.page, chunk.content) for chunk in chunks] == [
        (1, "segurança pública"),
        (2, "educação básica"),
    ]


def test_rejects_pdf_without_extractable_text() -> None:
    with pytest.raises(PdfProcessingError, match="no extractable text"):
        extract_pages(make_pdf(""))
