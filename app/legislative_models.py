from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


MAX_LEGISLATIVE_INPUT_CHARACTERS = 60_000


class LegislativeHouse(str, Enum):
    """Casas legislativas aceitas pelo contrato com o backend."""

    CAMARA = "CAMARA"
    SENADO = "SENADO"


class VotingObjectType(str, Enum):
    """Natureza do objeto específico submetido à votação."""

    URGENCY = "URGENCY"
    AMENDMENT = "AMENDMENT"
    SUBSTITUTE = "SUBSTITUTE"
    MAIN_TEXT = "MAIN_TEXT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class LegislativeImpactDirection(str, Enum):
    """Direção possível do impacto, sem avaliação partidária ou recomendação."""

    POSSIBLE_BENEFIT = "POSSIBLE_BENEFIT"
    POSSIBLE_COST = "POSSIBLE_COST"
    MIXED = "MIXED"
    UNCERTAIN = "UNCERTAIN"


class LegislativeProposalInput(BaseModel):
    """Proposta oficial relacionada à votação, sem buscar dados externos."""

    model_config = ConfigDict(str_strip_whitespace=True)

    identification: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=12_000)
    official_urls: list[HttpUrl] = Field(
        alias="officialUrls",
        min_length=1,
        max_length=10,
    )


class VotingDescriptionInput(BaseModel):
    """Descrição do objeto exato votado, já normalizada pelo backend."""

    model_config = ConfigDict(str_strip_whitespace=True)

    type: VotingObjectType = VotingObjectType.UNKNOWN
    identification: str | None = Field(default=None, max_length=120)
    description: str = Field(min_length=1, max_length=16_000)


class VotingTotalsInput(BaseModel):
    """Totais coletivos oficiais, quando a fonte os disponibilizar."""

    model_config = ConfigDict(populate_by_name=True)

    yes: int | None = Field(default=None, ge=0)
    no: int | None = Field(default=None, ge=0)
    abstention: int | None = Field(default=None, ge=0)
    obstruction: int | None = Field(default=None, ge=0)
    other: int | None = Field(default=None, ge=0)


class OriginalVotingResultInput(BaseModel):
    """Resultado coletivo exatamente como interpretado pela fonte oficial."""

    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4_000)
    totals: VotingTotalsInput | None = None


class LegislativeAffectedProfile(BaseModel):
    """Perfil hipotético sustentado pelas propostas oficiais recebidas."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    profile: str = Field(min_length=1, max_length=120)
    possible_impact: str = Field(
        alias="possibleImpact",
        min_length=1,
        max_length=400,
    )
    impact_direction: LegislativeImpactDirection = Field(alias="impactDirection")
    conditions: str | None = Field(default=None, max_length=300)


class LegislativeVoteExplanationRequest(BaseModel):
    """Dados oficiais suficientes para explicar uma votação sem consultar banco."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    house: LegislativeHouse
    voting_id: str = Field(alias="votingId", min_length=1, max_length=120)
    proposals: list[LegislativeProposalInput] = Field(
        min_length=1,
        max_length=20,
    )
    voting_description: VotingDescriptionInput = Field(alias="votingDescription")
    original_result: OriginalVotingResultInput | None = Field(
        default=None,
        alias="originalResult",
    )
    secret: bool | None = None
    official_result_code_mappings: dict[str, str] = Field(
        default_factory=dict,
        alias="officialResultCodeMappings",
    )

    @model_validator(mode="after")
    def validate_result_mappings(self) -> "LegislativeVoteExplanationRequest":
        if len(self.official_result_code_mappings) > 50:
            raise ValueError("officialResultCodeMappings accepts at most 50 entries")
        for code, meaning in self.official_result_code_mappings.items():
            if not code.strip() or len(code) > 100:
                raise ValueError("result mapping codes must contain 1 to 100 characters")
            if not meaning.strip() or len(meaning) > 1_000:
                raise ValueError("result mapping descriptions must contain 1 to 1000 characters")
        if len(self.model_dump_json(by_alias=True)) > MAX_LEGISLATIVE_INPUT_CHARACTERS:
            raise ValueError(
                f"request exceeds {MAX_LEGISLATIVE_INPUT_CHARACTERS} characters"
            )
        return self


class LegislativeVoteExplanationResponse(BaseModel):
    """Explicação curta e validada devolvida ao backend."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=160)
    proposal_explanation: str = Field(
        alias="proposalExplanation",
        min_length=1,
        max_length=3_000,
    )
    voting_explanation: str = Field(
        alias="votingExplanation",
        min_length=1,
        max_length=3_000,
    )
    result_explanation: str = Field(
        alias="resultExplanation",
        min_length=1,
        max_length=3_000,
    )
    limitations: list[Annotated[str, Field(min_length=1, max_length=1_000)]] = Field(
        default_factory=list,
        max_length=12,
    )
    affected_profiles: list[LegislativeAffectedProfile] = Field(
        alias="affectedProfiles",
        default_factory=list,
        max_length=3,
    )
    explanation_version: str = Field(
        alias="explanationVersion",
        min_length=1,
        max_length=80,
    )
