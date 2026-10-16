from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)


class NewsQuestionType(str, Enum):
    """Casos de uso aceitos pela rota de explicação de notícias."""

    EXPLAIN_NEWS = "EXPLAIN_NEWS"
    PEOPLE_MENTIONED = "PEOPLE_MENTIONED"
    HOW_IT_AFFECTS_ME = "HOW_IT_AFFECTS_ME"


class ImpactDirection(str, Enum):
    """Direção possível do impacto, sem emitir julgamento político."""

    POSSIBLE_BENEFIT = "POSSIBLE_BENEFIT"
    POSSIBLE_COST = "POSSIBLE_COST"
    MIXED = "MIXED"
    UNCERTAIN = "UNCERTAIN"


class NewsTimelineItem(BaseModel):
    """Evento opcional da linha do tempo recebido do BFF."""

    time: str | None = None
    title: str | None = None
    description: str | None = None


class NewsCandidate(BaseModel):
    """Candidato previamente associado à notícia pelo BFF."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    party: str | None = None
    mentioned_role: str | None = Field(default=None, alias="mentionedRole")


class NewsQuestionRequest(BaseModel):
    """Conteúdo completo necessário para responder sem buscar fontes externas."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    feed_id: int = Field(alias="feedId", gt=0)
    question_type: NewsQuestionType = Field(alias="questionType")
    title: str = Field(min_length=3)
    summary: str | None = None
    content: str = Field(min_length=20)
    contexts: list[str] = Field(default_factory=list)
    timeline: list[NewsTimelineItem] = Field(default_factory=list)
    candidates: list[NewsCandidate] = Field(default_factory=list)


class NewsPersonResponse(BaseModel):
    """Pessoa identificada e seu papel estritamente dentro da notícia."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    role_in_news: str = Field(alias="roleInNews", min_length=1)


class NewsAffectedProfileResponse(BaseModel):
    """Grupo hipotético que pode ser afetado segundo o conteúdo recebido."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    profile: str = Field(min_length=1, max_length=120)
    possible_impact: str = Field(
        alias="possibleImpact",
        min_length=1,
        max_length=400,
    )
    impact_direction: ImpactDirection = Field(alias="impactDirection")
    conditions: str | None = Field(default=None, max_length=300)


class NewsQuestionResponse(BaseModel):
    """Contrato único retornado ao BFF para os casos de uso de notícias."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    title: str = Field(min_length=1)
    answer: str | None = None
    people: list[NewsPersonResponse] = Field(default_factory=list)
    affected_profiles: list[NewsAffectedProfileResponse] | None = Field(
        default=None,
        alias="affectedProfiles",
        max_length=3,
    )
    limitations: list[str] | None = Field(default=None, max_length=3)

    @model_serializer(mode="wrap")
    def omit_unrelated_optional_sections(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict:
        """Não acrescenta campos novos às duas respostas legadas."""

        data = handler(self)
        if self.affected_profiles is None:
            data.pop("affected_profiles", None)
            data.pop("affectedProfiles", None)
        if self.limitations is None:
            data.pop("limitations", None)
        return data


class ExplainNewsOutput(NewsQuestionResponse):
    """Schema estruturado específico para uma explicação da notícia."""

    answer: str = Field(min_length=1)

    @model_validator(mode="after")
    def people_must_be_empty(self) -> "ExplainNewsOutput":
        if self.people:
            raise ValueError("people must be empty for EXPLAIN_NEWS")
        return self


class PeopleMentionedOutput(NewsQuestionResponse):
    """Schema estruturado específico para pessoas mencionadas."""

    answer: None = None


class HowItAffectsMeOutput(NewsQuestionResponse):
    """Resumo curto de impactos possíveis para perfis hipotéticos."""

    answer: str = Field(min_length=1, max_length=300)
    affected_profiles: list[NewsAffectedProfileResponse] = Field(
        alias="affectedProfiles",
        default_factory=list,
        max_length=3,
    )
    limitations: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def people_must_be_empty(self) -> "HowItAffectsMeOutput":
        if self.people:
            raise ValueError("people must be empty for HOW_IT_AFFECTS_ME")
        return self
