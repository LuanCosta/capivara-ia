from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)


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


class CompareRequest(BaseModel):
    """Identifica dois candidatos distintos usando candidates.id."""

    model_config = ConfigDict(populate_by_name=True)

    candidate_a_id: int = Field(alias="candidateAId", gt=0)
    candidate_b_id: int = Field(alias="candidateBId", gt=0)

    @model_validator(mode="after")
    def candidates_must_be_different(self) -> "CompareRequest":
        if self.candidate_a_id == self.candidate_b_id:
            raise ValueError("Candidates must be different")
        return self


class CandidateSummary(BaseModel):
    """Dados publicos do candidato retornados no comparativo."""

    id: int = Field(gt=0)
    name: str
    party: str
    number: int = Field(gt=0)
    image: str


class ThemeComparisonResponse(BaseModel):
    """Percentuais de um tema para os dois candidatos."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    title: str
    candidate_a_percent: int = Field(alias="candidateAPercent", ge=0, le=100)
    candidate_b_percent: int = Field(alias="candidateBPercent", ge=0, le=100)


class CompareResponse(BaseModel):
    """Resposta pequena consumida pelo grafico de radar."""

    model_config = ConfigDict(populate_by_name=True)

    candidate_a: CandidateSummary = Field(alias="candidateA")
    candidate_b: CandidateSummary = Field(alias="candidateB")
    themes: list[ThemeComparisonResponse]
    methodology: str


class DocumentAnalysisScores(BaseModel):
    """Índices temáticos calculados uma vez durante o processamento do plano."""

    economy: int = Field(ge=0, le=100)
    health: int = Field(ge=0, le=100)
    education: int = Field(ge=0, le=100)
    security: int = Field(ge=0, le=100)
    social: int = Field(ge=0, le=100)
    infrastructure: int = Field(ge=0, le=100)

    def as_list(self) -> list[int]:
        return [
            self.economy,
            self.health,
            self.education,
            self.security,
            self.social,
            self.infrastructure,
        ]


class ComparisonMaterial(BaseModel):
    """Candidato e análise persistida de seu plano mais recente."""

    candidate: CandidateSummary
    scores: DocumentAnalysisScores | None
