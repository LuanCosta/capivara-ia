import pytest
from fastapi.testclient import TestClient

from app.comparison import (
    ANALYSIS_INSTRUCTIONS,
    THEMES,
)
from app.config import Settings, get_settings
from app.main import app
from app.models import (
    CandidateSummary,
    ComparisonMaterial,
    DocumentAnalysisScores,
)
from app.repositories import get_document_repository


SECRET = "test-internal-secret"
EXPECTED_THEME_KEYS = [
    "economy",
    "health",
    "education",
    "security",
    "social",
    "infrastructure",
]


def _material(candidate_id: int) -> ComparisonMaterial:
    names = {13: "Lula", 9: "Romeu Zema"}
    parties = {13: "PT", 9: "Novo"}
    numbers = {13: 13, 9: 30}
    images = {13: "0xFFCC0000", 9: "0xFF000000"}
    return ComparisonMaterial(
        candidate=CandidateSummary(
            id=candidate_id,
            name=names[candidate_id],
            party=parties[candidate_id],
            number=numbers[candidate_id],
            image=images[candidate_id],
        ),
        scores=DocumentAnalysisScores(
            economy=45 if candidate_id == 13 else 40,
            health=40 if candidate_id == 13 else 35,
            education=40 if candidate_id == 13 else 50,
            security=35 if candidate_id == 13 else 45,
            social=40,
            infrastructure=40,
        ),
    )


class FakeComparisonRepository:
    def get_comparison_material(
        self, candidate_id: int
    ) -> ComparisonMaterial | None:
        return _material(candidate_id)


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-service-role-key",
        openai_api_key="test-openai-key",
        internal_api_secret=SECRET,
    )
    app.dependency_overrides[get_document_repository] = FakeComparisonRepository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_compare_returns_valid_comparison(client: TestClient) -> None:
    response = client.post(
        "/compare",
        headers={"X-Internal-Secret": SECRET},
        json={"candidateAId": 13, "candidateBId": 9},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidateA"] == {
        "id": 13,
        "name": "Lula",
        "party": "PT",
        "number": 13,
        "image": "0xFFCC0000",
    }
    assert body["candidateB"]["id"] == 9
    assert "qualidade" not in body["methodology"].lower()


def test_compare_rejects_same_candidate(client: TestClient) -> None:
    response = client.post(
        "/compare",
        headers={"X-Internal-Secret": SECRET},
        json={"candidateAId": 13, "candidateBId": 13},
    )

    assert response.status_code == 422


def test_compare_returns_not_found_for_unprocessed_candidate(
    client: TestClient,
) -> None:
    class MissingPlanRepository:
        def get_comparison_material(
            self, candidate_id: int
        ) -> ComparisonMaterial | None:
            return _material(13) if candidate_id == 13 else None

    app.dependency_overrides[get_document_repository] = MissingPlanRepository
    response = client.post(
        "/compare",
        headers={"X-Internal-Secret": SECRET},
        json={"candidateAId": 13, "candidateBId": 9},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Processed plan not found for candidate 9"
    }


@pytest.mark.parametrize("secret", [None, "invalid-secret-value"])
def test_compare_rejects_missing_or_invalid_secret(
    client: TestClient,
    secret: str | None,
) -> None:
    headers = {"X-Internal-Secret": secret} if secret is not None else {}
    response = client.post(
        "/compare",
        headers=headers,
        json={"candidateAId": 13, "candidateBId": 9},
    )

    assert response.status_code == 401


def test_document_scores_are_independent_and_do_not_need_to_sum_100() -> None:
    scores = DocumentAnalysisScores(
        economy=20,
        health=10,
        education=30,
        security=40,
        social=15,
        infrastructure=50,
    )

    assert scores.as_list() == [20, 10, 30, 40, 15, 50]
    assert sum(scores.as_list()) == 165


def test_analysis_prompt_forbids_external_knowledge_and_candidate_comparison() -> None:
    normalized = ANALYSIS_INSTRUCTIONS.lower()

    assert "não use conhecimento externo" in normalized
    assert "não compare candidatos" in normalized
    assert "não precisam somar 100" in normalized


def test_compare_reads_persisted_scores_without_calling_openai(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_created(settings: Settings) -> None:
        raise AssertionError("/compare must not create an OpenAI service")

    monkeypatch.setattr("app.main.create_comparison_service", fail_if_created)

    response = client.post(
        "/compare",
        headers={"X-Internal-Secret": SECRET},
        json={"candidateAId": 13, "candidateBId": 9},
    )

    assert response.status_code == 200


def test_compare_returns_exactly_the_six_expected_themes(
    client: TestClient,
) -> None:
    response = client.post(
        "/compare",
        headers={"X-Internal-Secret": SECRET},
        json={"candidateAId": 13, "candidateBId": 9},
    )

    assert response.status_code == 200
    themes = response.json()["themes"]
    assert [theme["key"] for theme in themes] == EXPECTED_THEME_KEYS
    assert [theme.key for theme in THEMES] == EXPECTED_THEME_KEYS
    assert all(0 <= theme["candidateAPercent"] <= 100 for theme in themes)
    assert all(0 <= theme["candidateBPercent"] <= 100 for theme in themes)
