from dataclasses import dataclass
from math import floor, sqrt
from typing import Protocol, Sequence

from app.config import Settings
from app.embeddings import EmbeddingError, create_embedding_service
from app.models import ComparisonMaterial


METHODOLOGY = (
    "Distribuição temática aproximada do conteúdo de cada plano. "
    "Zero indica que nenhum trecho foi associado ao tema."
)
THEME_SIMILARITY_WINDOW = 0.03


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
            best_similarity = max(similarities)
            related_theme_indexes = [
                index
                for index, similarity in enumerate(similarities)
                if best_similarity - similarity <= THEME_SIMILARITY_WINDOW
            ]

            # Um chunk pode tratar de mais de um tema. Nesse caso, seu tamanho
            # é dividido igualmente entre os temas semanticamente próximos.
            chunk_weight = len(chunk.content.strip())
            weight_per_theme = chunk_weight / len(related_theme_indexes)
            for index in related_theme_indexes:
                weights[index] += weight_per_theme

        if sum(weights) == 0:
            raise ComparisonAnalysisError(
                f"No classifiable content for candidate {material.candidate.id}"
            )

        return calculate_integer_percentages(weights)


def create_comparison_service(settings: Settings) -> ThemeComparisonService:
    """Monta o comparador com o mesmo cliente de embeddings do projeto."""

    return ThemeComparisonService(create_embedding_service(settings))


def calculate_integer_percentages(weights: Sequence[float]) -> list[int]:
    """Arredonda proporcionalmente preservando soma exata de 100."""

    total = sum(weights)
    if total <= 0:
        raise ValueError("At least one weight must be positive")

    exact = [(weight * 100) / total for weight in weights]
    percentages = [floor(value) for value in exact]
    remaining = 100 - sum(percentages)
    priority = sorted(
        range(len(weights)),
        key=lambda index: (exact[index] - percentages[index], weights[index]),
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
