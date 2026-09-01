import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.news_models import (
    NewsPersonResponse,
    NewsQuestionRequest,
    NewsQuestionResponse,
    NewsQuestionType,
)
from app.news_prompts import (
    build_explain_news_prompt,
    build_people_mentioned_prompt,
)
from app.news_service import NewsQuestionError


SECRET = "test-internal-secret"
BASE_BODY = {
    "feedId": 25,
    "questionType": "EXPLAIN_NEWS",
    "title": "Título da notícia",
    "summary": "Resumo da notícia",
    "content": "Conteúdo suficientemente completo para explicar a notícia.",
    "contexts": ["Informação de contexto"],
    "timeline": [],
    "candidates": [],
}


class FakeNewsQuestionService:
    async def answer(
        self, request: NewsQuestionRequest
    ) -> NewsQuestionResponse:
        if request.question_type is NewsQuestionType.EXPLAIN_NEWS:
            return NewsQuestionResponse(
                title="Explicando de forma simples",
                answer="A notícia relata um acontecimento de forma simples.",
                people=[],
            )
        return NewsQuestionResponse(
            title="Pessoas citadas",
            answer=None,
            people=[
                NewsPersonResponse(
                    name="Pessoa citada",
                    description="Descrição disponível na notícia.",
                    roleInNews="Participou do acontecimento relatado.",
                )
            ],
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-service-role-key",
        openai_api_key="test-openai-key",
        internal_api_secret=SECRET,
    )
    monkeypatch.setattr(
        "app.main.create_news_question_service",
        lambda settings: FakeNewsQuestionService(),
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_news_question_rejects_missing_secret(client: TestClient) -> None:
    response = client.post("/news/questions", json=BASE_BODY)

    assert response.status_code == 401


def test_news_question_rejects_invalid_question_type(client: TestClient) -> None:
    body = {**BASE_BODY, "questionType": "INVALID"}

    response = client.post(
        "/news/questions",
        headers={"X-Internal-Secret": SECRET},
        json=body,
    )

    assert response.status_code == 422


def test_news_question_rejects_short_content(client: TestClient) -> None:
    body = {**BASE_BODY, "content": "Muito curto"}

    response = client.post(
        "/news/questions",
        headers={"X-Internal-Secret": SECRET},
        json=body,
    )

    assert response.status_code == 422


def test_explain_news_returns_answer(client: TestClient) -> None:
    response = client.post(
        "/news/questions",
        headers={"X-Internal-Secret": SECRET},
        json=BASE_BODY,
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": "Explicando de forma simples",
        "answer": "A notícia relata um acontecimento de forma simples.",
        "people": [],
    }


def test_people_mentioned_returns_structured_list(client: TestClient) -> None:
    body = {**BASE_BODY, "questionType": "PEOPLE_MENTIONED"}

    response = client.post(
        "/news/questions",
        headers={"X-Internal-Secret": SECRET},
        json=body,
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": "Pessoas citadas",
        "answer": None,
        "people": [
            {
                "name": "Pessoa citada",
                "description": "Descrição disponível na notícia.",
                "roleInNews": "Participou do acontecimento relatado.",
            }
        ],
    }


def test_people_mentioned_accepts_empty_list(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class EmptyPeopleService:
        async def answer(
            self, request: NewsQuestionRequest
        ) -> NewsQuestionResponse:
            return NewsQuestionResponse(
                title="Pessoas citadas",
                answer=None,
                people=[],
            )

    monkeypatch.setattr(
        "app.main.create_news_question_service",
        lambda settings: EmptyPeopleService(),
    )
    response = client.post(
        "/news/questions",
        headers={"X-Internal-Secret": SECRET},
        json={**BASE_BODY, "questionType": "PEOPLE_MENTIONED"},
    )

    assert response.status_code == 200
    assert response.json()["people"] == []
    assert response.json()["answer"] is None


def test_news_question_returns_bad_gateway_when_openai_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingNewsService:
        async def answer(self, request: NewsQuestionRequest) -> None:
            raise NewsQuestionError("OpenAI timeout")

    monkeypatch.setattr(
        "app.main.create_news_question_service",
        lambda settings: FailingNewsService(),
    )
    response = client.post(
        "/news/questions",
        headers={"X-Internal-Secret": SECRET},
        json=BASE_BODY,
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Could not answer news question"}


def test_news_prompts_are_separate_and_forbid_external_knowledge() -> None:
    request = NewsQuestionRequest.model_validate(BASE_BODY)

    explain_prompt = build_explain_news_prompt(request)
    people_prompt = build_people_mentioned_prompt(
        request.model_copy(
            update={"question_type": NewsQuestionType.PEOPLE_MENTIONED}
        )
    )

    assert "Explique o que aconteceu" in explain_prompt
    assert "Não pesquise" in explain_prompt
    assert "Remova nomes duplicados" in people_prompt
    assert "não atribua cargos não confirmados" in people_prompt
