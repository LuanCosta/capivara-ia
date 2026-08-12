from dataclasses import dataclass
from typing import Protocol

from openai import AsyncOpenAI, OpenAIError

from app.config import Settings
from app.pdf_processing import ProposalChunk


EMBEDDING_DIMENSIONS = 1_536
EMBEDDING_BATCH_SIZE = 50


class EmbeddingError(Exception):
    """Indica falha na geração ou validação dos vetores."""


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    page: int
    content: str
    embedding: list[float]


class EmbeddingsEndpoint(Protocol):
    async def create(self, **kwargs: object) -> object: ...


class EmbeddingClient(Protocol):
    embeddings: EmbeddingsEndpoint


class EmbeddingService:
    """Gera embeddings em lotes e preserva a relação com cada chunk."""

    def __init__(self, client: EmbeddingClient, model: str) -> None:
        self._client = client
        self._model = model

    async def embed_text(self, text: str) -> list[float]:
        """Gera o vetor de um único texto, como a pergunta do usuário."""

        vectors = await self._embed_texts([text])
        if len(vectors) != 1:
            raise EmbeddingError("OpenAI returned an unexpected embedding count")
        return vectors[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Gera vetores para uma pequena colecao de textos em uma chamada."""

        if not texts:
            return []
        return await self._embed_texts(texts)

    async def embed_chunks(
        self, chunks: list[ProposalChunk]
    ) -> list[EmbeddedChunk]:
        embedded_chunks: list[EmbeddedChunk] = []

        for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
            vectors = await self._embed_texts([chunk.content for chunk in batch])

            if len(vectors) != len(batch):
                raise EmbeddingError("OpenAI returned an unexpected embedding count")

            embedded_chunks.extend(
                EmbeddedChunk(
                    page=chunk.page,
                    content=chunk.content,
                    embedding=vector,
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            )

        return embedded_chunks

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=EMBEDDING_DIMENSIONS,
                encoding_format="float",
            )
        except OpenAIError as error:
            raise EmbeddingError("Could not generate embeddings") from error

        ordered_items = sorted(response.data, key=lambda item: item.index)  # type: ignore[attr-defined]
        vectors = [item.embedding for item in ordered_items]
        if any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
            raise EmbeddingError("OpenAI returned an unexpected embedding dimension")

        return vectors


def create_embedding_service(settings: Settings) -> EmbeddingService:
    """Monta o serviço somente quando o fluxo realmente precisar da OpenAI."""

    if not settings.openai_api_key:
        raise EmbeddingError("OpenAI is not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    return EmbeddingService(client, settings.openai_embedding_model)
