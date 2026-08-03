from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.repositories import get_document_repository


class MissingDocumentRepository:
    def get_by_id(self, document_id: int) -> None:
        return None


def test_process_returns_not_found_when_document_does_not_exist() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
            internal_api_secret="test-internal-secret"
    )
    app.dependency_overrides[get_document_repository] = MissingDocumentRepository

    try:
        with TestClient(app) as client:
            response = client.post(
                "/documents/999/process",
                headers={"X-Internal-Secret": "test-internal-secret"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}
