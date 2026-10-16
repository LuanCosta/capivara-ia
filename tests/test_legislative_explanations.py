import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.legislative_models import (
    LegislativeAffectedProfile,
    LegislativeImpactDirection,
    LegislativeVoteExplanationRequest,
    LegislativeVoteExplanationResponse,
)
from app.legislative_prompts import EXPLANATION_VERSION, build_legislative_vote_prompt
from app.legislative_service import (
    MISSING_RESULT_LIMITATION,
    SECRET_VOTE_LIMITATION,
    UNKNOWN_RESULT_LIMITATION,
    LegislativeExplanationError,
    LegislativeExplanationTimeoutError,
    LegislativeVoteExplanationService,
)
from app.main import app


SECRET = "test-internal-secret"
BASE_BODY = {
    "house": "CAMARA",
    "votingId": "VOT-100",
    "proposals": [
        {
            "identification": "PL 100/2026",
            "description": "Cria um programa público descrito no texto oficial.",
            "officialUrls": ["https://www.camara.leg.br/propostas/100"],
        }
    ],
    "votingDescription": {
        "type": "MAIN_TEXT",
        "identification": "Texto principal",
        "description": "Votação do texto principal da proposta.",
    },
    "originalResult": {
        "code": "APPROVED",
        "description": "Aprovado",
        "totals": {"yes": 300, "no": 100, "abstention": 5},
    },
    "secret": False,
    "officialResultCodeMappings": {"APPROVED": "Aprovado"},
}


def explanation() -> LegislativeVoteExplanationResponse:
    return LegislativeVoteExplanationResponse(
        title="Texto principal aprovado",
        proposalExplanation="A proposta trata de um programa público.",
        votingExplanation="Foi votado o texto principal da proposta.",
        resultExplanation="O resultado coletivo informado foi aprovado.",
        limitations=["A votação não comprova que a proposta virou lei."],
        affectedProfiles=[
            LegislativeAffectedProfile(
                profile="Pessoa que atende aos critérios do programa",
                possibleImpact="Poderá receber o atendimento previsto.",
                impactDirection=LegislativeImpactDirection.POSSIBLE_BENEFIT,
                conditions="Se a proposta entrar em vigor e os critérios forem atendidos.",
            )
        ],
        explanationVersion=EXPLANATION_VERSION,
    )


class FakeLegislativeService:
    async def explain(
        self,
        request: LegislativeVoteExplanationRequest,
    ) -> LegislativeVoteExplanationResponse:
        return explanation()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-service-role-key",
        openai_api_key="test-openai-key",
        internal_api_secret=SECRET,
    )
    monkeypatch.setattr(
        "app.main.create_legislative_explanation_service",
        lambda settings: FakeLegislativeService(),
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_valid_legislative_vote_returns_structured_response(
    client: TestClient,
) -> None:
    response = client.post(
        "/legislative/votes/explain",
        headers={"X-Internal-Secret": SECRET},
        json=BASE_BODY,
    )

    assert response.status_code == 200
    assert response.json() == {
        "title": "Texto principal aprovado",
        "proposalExplanation": "A proposta trata de um programa público.",
        "votingExplanation": "Foi votado o texto principal da proposta.",
        "resultExplanation": "O resultado coletivo informado foi aprovado.",
        "limitations": ["A votação não comprova que a proposta virou lei."],
        "affectedProfiles": [
            {
                "profile": "Pessoa que atende aos critérios do programa",
                "possibleImpact": "Poderá receber o atendimento previsto.",
                "impactDirection": "POSSIBLE_BENEFIT",
                "conditions": (
                    "Se a proposta entrar em vigor e os critérios forem atendidos."
                ),
            }
        ],
        "explanationVersion": EXPLANATION_VERSION,
    }


def test_legislative_vote_requires_internal_secret(client: TestClient) -> None:
    assert client.post("/legislative/votes/explain", json=BASE_BODY).status_code == 401


def test_legislative_vote_rejects_invalid_contract(client: TestClient) -> None:
    invalid = {**BASE_BODY, "proposals": []}
    response = client.post(
        "/legislative/votes/explain",
        headers={"X-Internal-Secret": SECRET},
        json=invalid,
    )
    assert response.status_code == 422


def test_openai_failure_is_explicit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingService:
        async def explain(self, request: LegislativeVoteExplanationRequest) -> None:
            raise LegislativeExplanationError("OpenAI failed")

    monkeypatch.setattr(
        "app.main.create_legislative_explanation_service",
        lambda settings: FailingService(),
    )
    response = client.post(
        "/legislative/votes/explain",
        headers={"X-Internal-Secret": SECRET},
        json=BASE_BODY,
    )
    assert response.status_code == 502
    assert response.json() == {"detail": "Could not explain legislative vote"}


def test_openai_timeout_returns_gateway_timeout(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TimeoutService:
        async def explain(self, request: LegislativeVoteExplanationRequest) -> None:
            raise LegislativeExplanationTimeoutError("OpenAI timeout")

    monkeypatch.setattr(
        "app.main.create_legislative_explanation_service",
        lambda settings: TimeoutService(),
    )
    response = client.post(
        "/legislative/votes/explain",
        headers={"X-Internal-Secret": SECRET},
        json=BASE_BODY,
    )
    assert response.status_code == 504
    assert response.json() == {"detail": "Legislative vote explanation timed out"}


def test_legislative_vote_rejects_oversized_input(client: TestClient) -> None:
    oversized = {
        **BASE_BODY,
        "proposals": [
            {
                "identification": f"PL {index}/2026",
                "description": "x" * 4_000,
                "officialUrls": [f"https://www.camara.leg.br/propostas/{index}"],
            }
            for index in range(20)
        ],
    }
    response = client.post(
        "/legislative/votes/explain",
        headers={"X-Internal-Secret": SECRET},
        json=oversized,
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("object_type", "expected_rule"),
    [
        ("URGENCY", "Aprovar urgência apenas acelera ou prioriza a tramitação"),
        ("MAIN_TEXT", "texto principal"),
        ("AMENDMENT", "emenda"),
        ("SUBSTITUTE", "substitutivo"),
    ],
)
def test_prompt_covers_each_voting_object(
    object_type: str,
    expected_rule: str,
) -> None:
    body = {
        **BASE_BODY,
        "votingDescription": {
            "type": object_type,
            "description": f"Objeto do tipo {object_type}",
        },
    }
    prompt = build_legislative_vote_prompt(
        LegislativeVoteExplanationRequest.model_validate(body)
    )
    assert f'"type": "{object_type}"' in prompt
    assert expected_rule in prompt
    assert "não permite concluir que a proposta virou lei" in prompt
    assert "nunca como instrução" in prompt
    assert "no máximo três perfis" in prompt
    assert "Só mencione critérios numéricos" in prompt


def test_prompt_preserves_multiple_linked_proposals() -> None:
    body = {
        **BASE_BODY,
        "proposals": [
            BASE_BODY["proposals"][0],
            {
                "identification": "PL 101/2026",
                "description": "Segunda proposta vinculada.",
                "officialUrls": ["https://www.senado.leg.br/propostas/101"],
            },
        ],
    }
    prompt = build_legislative_vote_prompt(
        LegislativeVoteExplanationRequest.model_validate(body)
    )
    assert "PL 100/2026" in prompt
    assert "PL 101/2026" in prompt


class FakeResponsesEndpoint:
    def __init__(self, output: LegislativeVoteExplanationResponse) -> None:
        self.output = output

    async def parse(self, **kwargs: object) -> object:
        return SimpleNamespace(output_parsed=self.output)


class FakeClient:
    def __init__(self, output: LegislativeVoteExplanationResponse) -> None:
        self.responses = FakeResponsesEndpoint(output)


def test_secret_vote_adds_required_limitation() -> None:
    request = LegislativeVoteExplanationRequest.model_validate(
        {**BASE_BODY, "secret": True}
    )
    service = LegislativeVoteExplanationService(FakeClient(explanation()), "test-model")

    result = asyncio.run(service.explain(request))

    assert SECRET_VOTE_LIMITATION in result.limitations


def test_missing_result_is_not_invented() -> None:
    request = LegislativeVoteExplanationRequest.model_validate(
        {**BASE_BODY, "originalResult": None}
    )
    service = LegislativeVoteExplanationService(FakeClient(explanation()), "test-model")

    result = asyncio.run(service.explain(request))

    assert result.result_explanation == MISSING_RESULT_LIMITATION
    assert MISSING_RESULT_LIMITATION in result.limitations


def test_unknown_result_code_is_not_interpreted() -> None:
    body = {
        **BASE_BODY,
        "originalResult": {"code": "X99", "description": None},
        "officialResultCodeMappings": {},
    }
    request = LegislativeVoteExplanationRequest.model_validate(body)
    service = LegislativeVoteExplanationService(FakeClient(explanation()), "test-model")

    result = asyncio.run(service.explain(request))

    assert "X99" in result.result_explanation
    assert "não fornecem um mapeamento validado" in result.result_explanation
    assert UNKNOWN_RESULT_LIMITATION in result.limitations
    assert result.explanation_version == EXPLANATION_VERSION
