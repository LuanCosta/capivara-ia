import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.answering import (
    NOT_FOUND_ANSWER,
    AnswerGenerationError,
    create_answer_service,
)
from app.config import Settings, get_settings
from app.comparison import (
    METHODOLOGY,
    THEMES,
    ComparisonAnalysisError,
    create_comparison_service,
)
from app.embeddings import EmbeddingError, create_embedding_service
from app.models import (
    AskRequest,
    AskResponse,
    CompareRequest,
    CompareResponse,
    HealthResponse,
    ProcessResponse,
    SourceResponse,
    ThemeComparisonResponse,
)
from app.pdf_processing import (
    PdfDownloadError,
    PdfProcessingError,
    download_pdf,
    extract_and_chunk_pdf,
)
from app.repositories import ProposalDocumentRepository, get_document_repository
from app.security import require_internal_secret


logger = logging.getLogger("uvicorn.error")


app = FastAPI(
    title="Capivara Proposals AI",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Informa que o processo HTTP está pronto para receber requisições."""

    return HealthResponse(status="ok")


@app.post(
    "/documents/{document_id}/process",
    response_model=ProcessResponse,
    dependencies=[Depends(require_internal_secret)],
)
async def process_document(
    document_id: int,
    repository: Annotated[
        ProposalDocumentRepository, Depends(get_document_repository)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProcessResponse:
    """Busca o documento que será processado nas próximas etapas."""

    document = await run_in_threadpool(repository.get_by_id, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        pdf_bytes = await download_pdf(str(document.document_url))
        chunks = await run_in_threadpool(extract_and_chunk_pdf, pdf_bytes)
    except PdfDownloadError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except PdfProcessingError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    try:
        embedding_service = create_embedding_service(settings)
        embedded_chunks = await embedding_service.embed_chunks(chunks)
    except EmbeddingError as error:
        logger.exception(
            "Embedding generation failed for document %s",
            document_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    await run_in_threadpool(
        repository.replace_chunks,
        document.id,
        embedded_chunks,
    )

    return ProcessResponse(
        documentId=document.id,
        chunksProcessed=len(embedded_chunks),
    )


@app.post(
    "/ask",
    response_model=AskResponse,
    dependencies=[Depends(require_internal_secret)],
)
async def ask(
    request: AskRequest,
    repository: Annotated[
        ProposalDocumentRepository, Depends(get_document_repository)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AskResponse:
    """Busca as fontes da pergunta; a resposta por IA virá na próxima etapa."""

    try:
        embedding_service = create_embedding_service(settings)
        question_embedding = await embedding_service.embed_text(request.question)
    except EmbeddingError as error:
        logger.exception(
            "Question embedding failed for candidate %s",
            request.candidate_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    chunks = await run_in_threadpool(
        repository.match_chunks,
        request.candidate_id,
        question_embedding,
    )
    if not chunks:
        return AskResponse(
            answer=NOT_FOUND_ANSWER,
            sources=[],
        )

    try:
        answer_service = create_answer_service(settings)
        generated = await answer_service.generate(request.question, chunks)
    except AnswerGenerationError as error:
        logger.exception(
            "Answer generation failed for candidate %s",
            request.candidate_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    used_chunks = [
        chunks_by_id[source_id]
        for source_id in dict.fromkeys(generated.source_ids)
        if source_id in chunks_by_id
    ]
    if not used_chunks:
        return AskResponse(answer=NOT_FOUND_ANSWER, sources=[])

    sources = [
        SourceResponse(
            page=chunk.page,
            excerpt=chunk.content,
            documentUrl=str(chunk.document_url),
        )
        for chunk in used_chunks
    ]

    return AskResponse(
        answer=generated.answer,
        sources=sources,
    )


@app.post(
    "/compare",
    response_model=CompareResponse,
    dependencies=[Depends(require_internal_secret)],
)
async def compare(
    request: CompareRequest,
    repository: Annotated[
        ProposalDocumentRepository, Depends(get_document_repository)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CompareResponse:
    """Mede o detalhamento de execução de dois planos processados."""

    logger.info(
        "Starting proposal comparison: candidate_a=%s candidate_b=%s",
        request.candidate_a_id,
        request.candidate_b_id,
    )

    try:
        material_a = await run_in_threadpool(
            repository.get_comparison_material,
            request.candidate_a_id,
        )
        material_b = await run_in_threadpool(
            repository.get_comparison_material,
            request.candidate_b_id,
        )
    except Exception as error:
        logger.exception(
            "Database error during comparison: candidate_a=%s candidate_b=%s",
            request.candidate_a_id,
            request.candidate_b_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not load comparison data",
        ) from error

    for candidate_id, material in (
        (request.candidate_a_id, material_a),
        (request.candidate_b_id, material_b),
    ):
        if material is None or not material.chunks:
            logger.info(
                "Processed plan not found for comparison candidate=%s",
                candidate_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Processed plan not found for candidate {candidate_id}",
            )

    try:
        comparison_service = create_comparison_service(settings)
        percentages_a, percentages_b = await comparison_service.compare(
            material_a,
            material_b,
        )
    except (EmbeddingError, ComparisonAnalysisError) as error:
        logger.exception(
            "OpenAI comparison error: candidate_a=%s candidate_b=%s",
            request.candidate_a_id,
            request.candidate_b_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not analyze proposal details",
        ) from error

    themes = [
        ThemeComparisonResponse(
            key=theme.key,
            title=theme.title,
            candidateAPercent=percentages_a[index],
            candidateBPercent=percentages_b[index],
        )
        for index, theme in enumerate(THEMES)
    ]

    logger.info(
        "Proposal comparison completed: candidate_a=%s candidate_b=%s",
        request.candidate_a_id,
        request.candidate_b_id,
    )
    return CompareResponse(
        candidateA=material_a.candidate,
        candidateB=material_b.candidate,
        themes=themes,
        methodology=METHODOLOGY,
    )
