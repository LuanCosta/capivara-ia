from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class HealthResponse(BaseModel):
    """Resposta estável e tipada do health check."""

    status: Literal["ok"]


class AskRequest(BaseModel):
    """Dados necessários para buscar propostas de um candidato."""

    model_config = ConfigDict(populate_by_name=True)

    candidate_id: int = Field(alias="candidateId", gt=0)
    question: str = Field(min_length=3, max_length=2_000)


class SourceResponse(BaseModel):
    """Trecho do documento usado para sustentar uma resposta."""

    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(gt=0)
    excerpt: str
    document_url: str = Field(alias="documentUrl")


class AskResponse(BaseModel):
    """Resposta final acompanhada obrigatoriamente de suas fontes."""

    answer: str
    sources: list[SourceResponse]


class ProcessResponse(BaseModel):
    """Resumo do processamento concluído de um documento."""

    model_config = ConfigDict(populate_by_name=True)

    document_id: int = Field(alias="documentId", gt=0)
    chunks_processed: int = Field(alias="chunksProcessed", ge=0)


class ProposalDocument(BaseModel):
    """Representa um plano de governo armazenado no Supabase."""

    id: int
    candidate_id: int
    title: str
    document_url: HttpUrl
    source_url: HttpUrl
    election_year: int
    created_at: datetime


class RetrievedChunk(BaseModel):
    """Chunk retornado pela busca vetorial do PostgreSQL."""

    chunk_id: int
    document_id: int
    page: int
    content: str
    document_url: HttpUrl
    similarity: float
