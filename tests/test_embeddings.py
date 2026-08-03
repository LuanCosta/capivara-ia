import asyncio
from dataclasses import dataclass

import pytest

from app.embeddings import EMBEDDING_DIMENSIONS, EmbeddingError, EmbeddingService
from app.pdf_processing import ProposalChunk


@dataclass
class FakeEmbeddingItem:
    index: int
    embedding: list[float]


@dataclass
class FakeEmbeddingResponse:
    data: list[FakeEmbeddingItem]


class FakeEmbeddingsEndpoint:
    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimensions = dimensions
        self.received_inputs: list[str] = []

    async def create(self, **kwargs: object) -> FakeEmbeddingResponse:
        inputs = kwargs["input"]
        assert isinstance(inputs, list)
        self.received_inputs.extend(inputs)
        return FakeEmbeddingResponse(
            data=[
                FakeEmbeddingItem(index=index, embedding=[0.1] * self.dimensions)
                for index, _ in enumerate(inputs)
            ]
        )


class FakeOpenAIClient:
    def __init__(self, endpoint: FakeEmbeddingsEndpoint) -> None:
        self.embeddings = endpoint


def test_embeds_chunks_and_preserves_source_data() -> None:
    endpoint = FakeEmbeddingsEndpoint()
    service = EmbeddingService(FakeOpenAIClient(endpoint), "text-embedding-3-small")
    chunks = [
        ProposalChunk(page=2, content="Primeira proposta"),
        ProposalChunk(page=7, content="Segunda proposta"),
    ]

    result = asyncio.run(service.embed_chunks(chunks))

    assert endpoint.received_inputs == ["Primeira proposta", "Segunda proposta"]
    assert [(item.page, item.content) for item in result] == [
        (2, "Primeira proposta"),
        (7, "Segunda proposta"),
    ]
    assert all(len(item.embedding) == EMBEDDING_DIMENSIONS for item in result)


def test_rejects_unexpected_embedding_dimension() -> None:
    endpoint = FakeEmbeddingsEndpoint(dimensions=10)
    service = EmbeddingService(FakeOpenAIClient(endpoint), "text-embedding-3-small")

    with pytest.raises(EmbeddingError, match="unexpected embedding dimension"):
        asyncio.run(
            service.embed_chunks([ProposalChunk(page=1, content="Proposta")])
        )


def test_embeds_single_question() -> None:
    endpoint = FakeEmbeddingsEndpoint()
    service = EmbeddingService(FakeOpenAIClient(endpoint), "text-embedding-3-small")

    vector = asyncio.run(service.embed_text("Qual é a proposta?"))

    assert endpoint.received_inputs == ["Qual é a proposta?"]
    assert len(vector) == EMBEDDING_DIMENSIONS
