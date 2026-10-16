import json
import hashlib
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from app.legislative_classification.validate_schema import validate


MAX_CLASSIFICATION_INPUT_CHARACTERS = 250_000


class LegislativeClassificationRequest(BaseModel):
    """Registro oficial completo consumido pelas regras determinísticas 1.1."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        str_strip_whitespace=False,
    )

    house: Literal["CAMARA", "SENADO"]
    voting_id: str = Field(alias="votingId", min_length=1, max_length=120)
    description: str = Field(max_length=30_000)
    result: dict[str, Any]
    proposal_references: list[dict[str, Any]] = Field(
        alias="proposalReferences",
        max_length=100,
    )
    possible_objects: list[dict[str, Any]] = Field(
        alias="possibleObjects",
        max_length=2_000,
    )
    registered_effects: list[dict[str, Any]] = Field(
        alias="registeredEffects",
        max_length=2_000,
    )
    affected_proposals: list[dict[str, Any]] = Field(
        alias="affectedProposals",
        max_length=100,
    )
    latest_voting_opening: dict[str, Any] = Field(alias="latestVotingOpening")
    event: dict[str, Any]
    organ: dict[str, Any]
    official_references: list[str] = Field(
        alias="officialReferences",
        min_length=1,
        max_length=100,
    )
    raw_metadata: dict[str, Any] = Field(alias="rawMetadata")

    @model_validator(mode="after")
    def validate_serialized_size(self) -> "LegislativeClassificationRequest":
        size = len(
            json.dumps(
                self.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        if size > MAX_CLASSIFICATION_INPUT_CHARACTERS:
            raise ValueError(
                f"request exceeds {MAX_CLASSIFICATION_INPUT_CHARACTERS} characters"
            )
        return self

    def to_classifier_record(self) -> dict[str, Any]:
        """Preserva aliases e metadados extras usados no hash de proveniência."""

        return self.model_dump(mode="json", by_alias=True)


class LegislativeClassificationResponse(RootModel[dict[str, Any]]):
    """Resposta validada integralmente pelo JSON Schema 1.1 empacotado."""

    @model_validator(mode="after")
    def validate_contract(self) -> "LegislativeClassificationResponse":
        validate(self.root, classification_schema())
        return self


@lru_cache
def classification_schema() -> dict[str, Any]:
    schema_path = files("app.legislative_classification").joinpath(
        "capivara_classificacao_contrato.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


@lru_cache
def classification_artifact_hash() -> str:
    """Fingerprint of the same official module manifest pinned by the Kotlin worker."""
    package = files("app.legislative_classification")
    names = ("classifier.py", "api_models.py", "validate_schema.py", "capivara_classificacao_contrato.json")
    manifest = {"app/legislative_classification/" + name:
                hashlib.sha256(package.joinpath(name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for name in names}
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
