import asyncio
from types import SimpleNamespace

from app.answering import AnswerService, GeneratedAnswer
from app.models import RetrievedChunk


class FakeResponsesEndpoint:
    def __init__(self) -> None:
        self.arguments: dict[str, object] = {}

    async def parse(self, **kwargs: object) -> object:
        self.arguments = kwargs
        return SimpleNamespace(
            output_parsed=GeneratedAnswer(
                answer="O plano propõe investir em prevenção e inteligência.",
                source_ids=[101],
            )
        )


class FakeAnswerClient:
    def __init__(self, endpoint: FakeResponsesEndpoint) -> None:
        self.responses = endpoint


def test_generates_concise_structured_answer_without_storage() -> None:
    endpoint = FakeResponsesEndpoint()
    service = AnswerService(FakeAnswerClient(endpoint), "gpt-4.1-mini")
    chunks = [
        RetrievedChunk(
            chunk_id=101,
            document_id=1,
            page=7,
            content="Investir em prevenção e inteligência policial.",
            document_url="https://example.com/document.pdf",
            similarity=0.9,
        )
    ]

    result = asyncio.run(service.generate("O que propõe para segurança?", chunks))

    assert result.source_ids == [101]
    assert "prevenção" in result.answer
    assert endpoint.arguments["model"] == "gpt-4.1-mini"
    assert endpoint.arguments["store"] is False
    assert endpoint.arguments["max_output_tokens"] == 300
    assert "O que propõe para segurança?" in str(endpoint.arguments["input"])
    assert "Investir em prevenção" in str(endpoint.arguments["input"])
