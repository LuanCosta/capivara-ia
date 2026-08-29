import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.answering import GeneratedAnswer
from app.embeddings import EmbeddedChunk
from app.main import app
from app.models import DocumentAnalysisScores, ProposalDocument, RetrievedChunk
from app.pdf_processing import ProposalChunk
from app.repositories import get_document_repository


class FakeDocumentRepository:
    def get_by_id(self, document_id: int) -> ProposalDocument | None:
        return ProposalDocument(
            id=document_id,
            candidate_id=13,
            title="Plano de governo",
            document_url="https://example.com/document.pdf",
            source_url="https://example.com/source",
            election_year=2026,
            created_at="2026-08-02T12:00:00Z",
        )

    def replace_chunks_and_analysis(
        self,
        document_id: int,
        chunks: list[EmbeddedChunk],
        scores: DocumentAnalysisScores,
        analysis_model: str,
        analysis_version: str,
    ) -> None:
        return None

    def match_chunks(
        self,
        candidate_id: int,
        query_embedding: list[float],
        match_count: int = 5,
    ) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id=1,
                document_id=10,
                page=7,
                content="Proposta encontrada",
                document_url="https://example.com/document.pdf",
                similarity=0.91,
            )
        ]


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-service-role-key",
        openai_api_key="test-openai-key",
        internal_api_secret="test-internal-secret"
    )
    app.dependency_overrides[get_document_repository] = FakeDocumentRepository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/documents/10/process", None),
        ("/ask", {"candidateId": 13, "question": "Qual é a proposta?"}),
        ("/compare", {"candidateAId": 13, "candidateBId": 9}),
    ],
)
def test_protected_routes_reject_missing_secret(
    client: TestClient, path: str, body: dict[str, object] | None
) -> None:
    response = client.post(path, json=body)

    assert response.status_code == 401


def test_valid_secret_reaches_process_handler(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_download_pdf(document_url: str) -> bytes:
        return b"%PDF-fake"

    class FakeEmbeddingService:
        async def embed_chunks(
            self, chunks: list[ProposalChunk]
        ) -> list[EmbeddedChunk]:
            return [
                EmbeddedChunk(
                    page=chunk.page,
                    content=chunk.content,
                    embedding=[0.1] * 1_536,
                )
                for chunk in chunks
            ]

    class FakeComparisonService:
        async def analyze(
            self, chunks: list[ProposalChunk]
        ) -> DocumentAnalysisScores:
            return DocumentAnalysisScores(
                economy=20,
                health=20,
                education=20,
                security=20,
                social=20,
                infrastructure=20,
            )

    monkeypatch.setattr("app.main.download_pdf", fake_download_pdf)
    monkeypatch.setattr(
        "app.main.extract_and_chunk_pdf",
        lambda pdf_bytes: [ProposalChunk(page=1, content="Proposta")],
    )
    monkeypatch.setattr(
        "app.main.create_embedding_service",
        lambda settings: FakeEmbeddingService(),
    )
    monkeypatch.setattr(
        "app.main.create_comparison_service",
        lambda settings: FakeComparisonService(),
    )

    response = client.post(
        "/documents/10/process",
        headers={"X-Internal-Secret": "test-internal-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"documentId": 10, "chunksProcessed": 1}


def test_ask_validates_request_body(client: TestClient) -> None:
    response = client.post(
        "/ask",
        headers={"X-Internal-Secret": "test-internal-secret"},
        json={"candidateId": 0, "question": ""},
    )

    assert response.status_code == 422


def test_ask_returns_retrieved_sources(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeQuestionEmbeddingService:
        async def embed_text(self, text: str) -> list[float]:
            return [0.1] * 1_536

    class FakeAnswerService:
        async def generate(
            self, question: str, chunks: list[RetrievedChunk]
        ) -> GeneratedAnswer:
            return GeneratedAnswer(
                answer="O plano apresenta uma proposta clara.",
                source_ids=[1],
            )

    monkeypatch.setattr(
        "app.main.create_embedding_service",
        lambda settings: FakeQuestionEmbeddingService(),
    )
    monkeypatch.setattr(
        "app.main.create_answer_service",
        lambda settings: FakeAnswerService(),
    )

    response = client.post(
        "/ask",
        headers={"X-Internal-Secret": "test-internal-secret"},
        json={
            "candidateId": 13,
            "question": "O que propõe para segurança?",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "O plano apresenta uma proposta clara."
    assert response.json()["sources"] == [
        {
            "page": 7,
            "excerpt": "Proposta encontrada",
            "documentUrl": "https://example.com/document.pdf",
        }
    ]
