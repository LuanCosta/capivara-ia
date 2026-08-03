from dataclasses import dataclass

import fitz
import httpx


MAX_PDF_BYTES = 25 * 1024 * 1024
CHUNK_MAX_CHARACTERS = 1_800
CHUNK_OVERLAP_CHARACTERS = 250


class PdfDownloadError(Exception):
    """Indica que o PDF remoto não pôde ser obtido com segurança."""


class PdfProcessingError(Exception):
    """Indica que o arquivo não é um PDF textual processável."""


@dataclass(frozen=True, slots=True)
class PageText:
    page: int
    content: str


@dataclass(frozen=True, slots=True)
class ProposalChunk:
    page: int
    content: str


async def download_pdf(document_url: str) -> bytes:
    """Baixa um PDF remoto e aplica limites adequados ao MVP."""

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
        ) as client:
            response = await client.get(document_url)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise PdfDownloadError("Could not download document") from error

    pdf_bytes = response.content
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise PdfDownloadError("Document exceeds the 25 MB limit")
    if not pdf_bytes.startswith(b"%PDF"):
        raise PdfDownloadError("Downloaded file is not a PDF")

    return pdf_bytes


def extract_pages(pdf_bytes: bytes) -> list[PageText]:
    """Extrai texto por página sem executar OCR."""

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            pages = [
                PageText(page=index, content=page.get_text("text").strip())
                for index, page in enumerate(document, start=1)
            ]
    except (fitz.FileDataError, RuntimeError, ValueError) as error:
        raise PdfProcessingError("Could not read PDF") from error

    pages_with_text = [page for page in pages if page.content]
    if not pages_with_text:
        raise PdfProcessingError("PDF has no extractable text")

    return pages_with_text


def build_chunks(pages: list[PageText]) -> list[ProposalChunk]:
    """Divide o texto sem misturar conteúdo de páginas diferentes."""

    chunks: list[ProposalChunk] = []
    for page in pages:
        words = page.content.split()
        current_words: list[str] = []

        for word in words:
            candidate = " ".join([*current_words, word])
            if current_words and len(candidate) > CHUNK_MAX_CHARACTERS:
                chunks.append(
                    ProposalChunk(page=page.page, content=" ".join(current_words))
                )
                current_words = _overlap_words(current_words)

            current_words.append(word)

        if current_words:
            chunks.append(
                ProposalChunk(page=page.page, content=" ".join(current_words))
            )

    return chunks


def extract_and_chunk_pdf(pdf_bytes: bytes) -> list[ProposalChunk]:
    """Executa as duas transformações locais na ordem correta."""

    return build_chunks(extract_pages(pdf_bytes))


def _overlap_words(words: list[str]) -> list[str]:
    overlap: list[str] = []
    character_count = 0

    for word in reversed(words):
        additional_characters = len(word) + (1 if overlap else 0)
        if character_count + additional_characters > CHUNK_OVERLAP_CHARACTERS:
            break
        overlap.append(word)
        character_count += additional_characters

    overlap.reverse()
    return overlap
