from dataclasses import dataclass
from math import exp, floor, sqrt
from typing import Protocol, Sequence

from app.config import Settings
from app.embeddings import EmbeddingError, create_embedding_service
from app.models import ComparisonMaterial


METHODOLOGY = (
    "Distribuição aproximada da afinidade semântica do conteúdo de cada "
    "plano entre os seis temas."
)
SIMILARITY_TEMPERATURE = 0.10


@dataclass(frozen=True, slots=True)
class ThemeDefinition:
    key: str
    title: str
    description: str


THEMES = (
    ThemeDefinition(
        "economy",
        "Economia",
        "economia, emprego, renda, impostos, indústria, comércio, agricultura e finanças",
    ),
    ThemeDefinition(
        "health",
        "Saúde",
        "saúde pública, hospitais, atendimento médico, medicamentos, prevenção e SUS",
    ),
    ThemeDefinition(
        "education",
        "Educação",
        "educação, escolas, universidades, professores, ensino, pesquisa e formação",
    ),
    ThemeDefinition(
        "security",
        "Segurança",
        "segurança pública, polícia, violência, justiça criminal, drogas e sistema prisional",
    ),
    ThemeDefinition(
        "social",
        "Social",
        "assistência social, pobreza, direitos humanos, igualdade, habitação e inclusão",
    ),
    ThemeDefinition(
        "infrastructure",
        "Infraestrutura",
        "infraestrutura, transporte, energia, saneamento, obras, logística e conectividade",
    ),
)


class TextEmbeddingService(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class ComparisonAnalysisError(Exception):
    """Indica que a distribuicao tematica nao pode ser calculada."""


class ThemeComparisonService:
    """Classifica embeddings existentes e calcula percentuais inteiros."""

    def __init__(self, embedding_service: TextEmbeddingService) -> None:
        self._embedding_service = embedding_service

    async def compare(
        self,
        candidate_a: ComparisonMaterial,
        candidate_b: ComparisonMaterial,
    ) -> tuple[list[int], list[int]]:
        try:
            theme_embeddings = await self._embedding_service.embed_texts(
                [theme.description for theme in THEMES]
            )
        except EmbeddingError as error:
            raise ComparisonAnalysisError(
                "Could not classify comparison themes"
            ) from error

        if len(theme_embeddings) != len(THEMES):
            raise ComparisonAnalysisError(
                "OpenAI returned an unexpected theme embedding count"
            )

        return (
            self._analyze(candidate_a, theme_embeddings),
            self._analyze(candidate_b, theme_embeddings),
        )

    def _analyze(
        self,
        material: ComparisonMaterial,
        theme_embeddings: list[list[float]],
    ) -> list[int]:
        weights = [0.0] * len(THEMES)

        for chunk in material.chunks:
            similarities = [
                _cosine_similarity(chunk.embedding, theme_embedding)
                for theme_embedding in theme_embeddings
            ]
            # Softmax transforma as similaridades em pesos relativos. Subtrair
            # o maior valor manté o cálculo numericamente estável.
            best_similarity = max(similarities)
            semantic_weights = [
                exp(
                    (similarity - best_similarity)
                    / SIMILARITY_TEMPERATURE
                )
                for similarity in similarities
            ]
            semantic_weight_total = sum(semantic_weights)
            chunk_weight = len(chunk.content.strip())
            for index, semantic_weight in enumerate(semantic_weights):
                weights[index] += (
                    chunk_weight * semantic_weight / semantic_weight_total
                )

        if sum(weights) == 0:
            raise ComparisonAnalysisError(
                f"No classifiable content for candidate {material.candidate.id}"
            )

        return calculate_integer_percentages(weights)


def create_comparison_service(settings: Settings) -> ThemeComparisonService:
    """Monta o comparador com o mesmo cliente de embeddings do projeto."""

    return ThemeComparisonService(create_embedding_service(settings))


def calculate_integer_percentages(weights: Sequence[float]) -> list[int]:
    """Arredonda pesos positivos preservando soma exata e zeros reais."""

    total = sum(weights)
    if total <= 0:
        raise ValueError("At least one weight must be positive")

    positive_count = sum(weight > 0 for weight in weights)
    distributable = 100 - positive_count
    exact = [(weight * distributable) / total for weight in weights]
    percentages = [
        (1 if weight > 0 else 0) + floor(value)
        for weight, value in zip(weights, exact, strict=True)
    ]
    remaining = 100 - sum(percentages)
    priority = sorted(
        (index for index, weight in enumerate(weights) if weight > 0),
        key=lambda index: (
            exact[index] - floor(exact[index]),
            weights[index],
        ),
        reverse=True,
    )

    for index in priority[:remaining]:
        percentages[index] += 1

    return percentages


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ComparisonAnalysisError("Embedding dimensions do not match")

    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)
