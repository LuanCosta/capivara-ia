import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.legislative_classification.api_models import classification_schema
from app.legislative_classification.classifier import official_data_hash
from app.legislative_classification.validate_schema import validate
from app.main import app


SECRET = "test-internal-secret"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "legislative_classification_cases.json"
RECORDS = {
    item["votingId"]: item
    for item in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["records"]
}


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="test-service-role-key",
        openai_api_key="test-openai-key",
        internal_api_secret=SECRET,
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def classify(client: TestClient, voting_id: str) -> dict:
    response = client.post(
        "/legislative/votes/classify",
        headers={"X-Internal-Secret": SECRET},
        json=RECORDS[voting_id],
    )
    assert response.status_code == 200, response.text
    output = response.json()
    validate(output, classification_schema())
    return output


def test_classification_requires_internal_secret(client: TestClient) -> None:
    response = client.post(
        "/legislative/votes/classify",
        json=RECORDS["2162116-169"],
    )
    assert response.status_code == 401


def test_classification_rejects_invalid_secret(client: TestClient) -> None:
    response = client.post(
        "/legislative/votes/classify",
        headers={"X-Internal-Secret": "invalid-internal-secret"},
        json=RECORDS["2162116-169"],
    )
    assert response.status_code == 401


def test_classification_accepts_valid_secret_and_preserves_provenance(
    client: TestClient,
) -> None:
    source = RECORDS["2162116-169"]
    output = classify(client, "2162116-169")

    assert output["schemaVersion"] == "1.1"
    assert output["classifierVersion"] == "rules-0.3.0"
    assert output["input"]["officialDataHash"] == official_data_hash(source)
    assert output["evidence"]
    assert output["annotationStatus"] == "AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED"
    assert output["publication"]["eligibility"] == "BLOCKED_PENDING_REVIEW"


def test_classification_rejects_incomplete_payload(client: TestClient) -> None:
    incomplete = deepcopy(RECORDS["2162116-169"])
    incomplete.pop("rawMetadata")
    response = client.post(
        "/legislative/votes/classify",
        headers={"X-Internal-Secret": SECRET},
        json=incomplete,
    )
    assert response.status_code == 422


def test_classification_rejects_invalid_payload(client: TestClient) -> None:
    invalid = {**RECORDS["2162116-169"], "house": "MUNICIPAL"}
    response = client.post(
        "/legislative/votes/classify",
        headers={"X-Internal-Secret": SECRET},
        json=invalid,
    )
    assert response.status_code == 422


def test_classification_rejects_oversized_payload(client: TestClient) -> None:
    oversized = deepcopy(RECORDS["2162116-169"])
    oversized["possibleObjects"] = [{"description": "x" * 250_000}]
    response = client.post(
        "/legislative/votes/classify",
        headers={"X-Internal-Secret": SECRET},
        json=oversized,
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("voting_id", "voting_type", "role", "stage", "review"),
    [
        ("2162116-161", "REQUIREMENT", "PROCEDURAL_DECISION", "UNKNOWN", True),
        ("2162116-169", "AMENDMENT", "MAIN_PROPOSAL_DECISION", "FIRST_ROUND", False),
        ("2162116-178", "BASE_TEXT", "MAIN_PROPOSAL_DECISION", "SECOND_ROUND", False),
        ("2233802-424", "AMENDMENT", "MAIN_PROPOSAL_DECISION", "FIRST_ROUND", True),
        ("2233802-438", "BASE_TEXT", "MAIN_PROPOSAL_DECISION", "SECOND_ROUND", False),
        ("2351506-104", "SUBSTITUTE_TEXT", "MAIN_PROPOSAL_DECISION", "FIRST_ROUND", False),
        ("2351506-108", "HIGHLIGHT", "PARTIAL_TEXT_DECISION", "UNKNOWN", True),
        ("2351506-122", "BASE_TEXT", "MAIN_PROPOSAL_DECISION", "SECOND_ROUND", False),
        ("2545792-26", "UNKNOWN", "INDETERMINATE", "UNKNOWN", True),
    ],
)
def test_real_legislative_cases(
    client: TestClient,
    voting_id: str,
    voting_type: str,
    role: str,
    stage: str,
    review: bool,
) -> None:
    output = classify(client, voting_id)
    classification = output["classification"]

    assert classification["votingType"] == voting_type
    assert classification["decisionRole"] == role
    assert classification["legislativeStage"] == stage
    assert classification["requiresHumanReview"] is review
    assert output["publication"]["eligibility"] == "BLOCKED_PENDING_REVIEW"


def test_classification_does_not_call_openai_or_supabase(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("external dependency was called")

    monkeypatch.setattr("app.main.create_legislative_explanation_service", forbidden)
    monkeypatch.setattr("app.main.create_embedding_service", forbidden)

    output = classify(client, "2351506-104")
    assert output["classification"]["votingType"] == "SUBSTITUTE_TEXT"


def test_schema_violation_returns_explicit_internal_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.main.classify_record",
        lambda record: {"schemaVersion": "invalid"},
    )
    response = client.post(
        "/legislative/votes/classify",
        headers={"X-Internal-Secret": SECRET},
        json=RECORDS["2162116-169"],
    )
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Legislative classification violated schema 1.1"
    }


def test_transport_preserves_original_whitespace_and_artifact(client: TestClient) -> None:
    from app.legislative_classification.api_models import classification_artifact_hash
    record = deepcopy(RECORDS["2162116-169"])
    record["description"] = " " + record["description"] + " "
    response = client.post("/legislative/votes/classify",
        headers={"X-Internal-Secret": SECRET}, json=record)
    assert response.status_code == 200
    assert response.json()["input"]["officialDataHash"] == official_data_hash(record)
    assert response.headers["X-Capivara-Classifier-Artifact"] == classification_artifact_hash()


def test_artifact_digest_is_portable_across_source_line_endings(monkeypatch) -> None:
    from types import SimpleNamespace
    import app.legislative_classification.api_models as models
    package = models.files("app.legislative_classification")
    models.classification_artifact_hash.cache_clear()
    expected = models.classification_artifact_hash()
    def joinpath(name):
        data = package.joinpath(name).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        return SimpleNamespace(read_bytes=lambda: data)
    try:
        with monkeypatch.context() as context:
            context.setattr(models, "files", lambda _: SimpleNamespace(joinpath=joinpath))
            models.classification_artifact_hash.cache_clear()
            assert models.classification_artifact_hash() == expected
    finally:
        models.classification_artifact_hash.cache_clear()
