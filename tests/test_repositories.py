from typing import Self

from app.embeddings import EmbeddedChunk
from app.models import DocumentAnalysisScores
from app.repositories import ProposalDocumentRepository


class EmptyQuery:
    def select(self, columns: str) -> Self:
        return self

    def eq(self, column: str, value: int) -> Self:
        return self

    def maybe_single(self) -> Self:
        return self

    def execute(self) -> None:
        return None


class EmptySupabaseClient:
    def table(self, table_name: str) -> EmptyQuery:
        return EmptyQuery()


class RpcQuery:
    def __init__(self) -> None:
        self.was_executed = False

    def execute(self) -> None:
        self.was_executed = True


class RecordingSupabaseClient:
    def __init__(self) -> None:
        self.function_name: str | None = None
        self.parameters: dict[str, object] | None = None
        self.query = RpcQuery()

    def rpc(
        self, function_name: str, parameters: dict[str, object]
    ) -> RpcQuery:
        self.function_name = function_name
        self.parameters = parameters
        return self.query


def test_get_by_id_accepts_none_response_for_missing_document() -> None:
    repository = ProposalDocumentRepository(EmptySupabaseClient())  # type: ignore[arg-type]

    document = repository.get_by_id(999)

    assert document is None


def test_replace_chunks_calls_transactional_database_function() -> None:
    client = RecordingSupabaseClient()
    repository = ProposalDocumentRepository(client)  # type: ignore[arg-type]
    chunks = [
        EmbeddedChunk(
            page=7,
            content="Proposta de segurança",
            embedding=[0.1] * 1_536,
        )
    ]

    repository.replace_chunks(document_id=13, chunks=chunks)

    assert client.function_name == "replace_proposal_chunks"
    assert client.parameters == {
        "target_document_id": 13,
        "new_chunks": [
            {
                "page": 7,
                "content": "Proposta de segurança",
                "embedding": [0.1] * 1_536,
            }
        ],
    }
    assert client.query.was_executed is True


def test_replace_chunks_and_analysis_calls_transactional_database_function() -> None:
    client = RecordingSupabaseClient()
    repository = ProposalDocumentRepository(client)  # type: ignore[arg-type]
    chunks = [
        EmbeddedChunk(page=7, content="Proposta", embedding=[0.1] * 1_536)
    ]
    scores = DocumentAnalysisScores(
        economy=45,
        health=40,
        education=35,
        security=30,
        social=25,
        infrastructure=20,
    )

    repository.replace_chunks_and_analysis(
        document_id=13,
        chunks=chunks,
        scores=scores,
        analysis_model="gpt-test",
        analysis_version="test-v1",
    )

    assert client.function_name == "replace_proposal_chunks_with_analysis"
    assert client.parameters == {
        "target_document_id": 13,
        "new_chunks": [
            {
                "page": 7,
                "content": "Proposta",
                "embedding": [0.1] * 1_536,
            }
        ],
        "new_analysis": scores.model_dump(),
        "analysis_model_name": "gpt-test",
        "analysis_version_name": "test-v1",
    }


def test_match_chunks_calls_candidate_filtered_rpc() -> None:
    client = RecordingSupabaseClient()
    repository = ProposalDocumentRepository(client)  # type: ignore[arg-type]

    result = repository.match_chunks(
        candidate_id=13,
        query_embedding=[0.2] * 1_536,
    )

    assert result == []
    assert client.function_name == "match_proposal_chunks"
    assert client.parameters == {
        "query_embedding": [0.2] * 1_536,
        "requested_candidate_id": 13,
        "match_count": 5,
    }
