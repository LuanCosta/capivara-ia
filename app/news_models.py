from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NewsQuestionType(str, Enum):
    """Casos de uso aceitos pela rota de explicação de notícias."""

    EXPLAIN_NEWS = "EXPLAIN_NEWS"
    PEOPLE_MENTIONED = "PEOPLE_MENTIONED"


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


class NewsQuestionResponse(BaseModel):
    """Contrato único retornado ao BFF para os dois tipos de pergunta."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1)
    answer: str | None = None
    people: list[NewsPersonResponse] = Field(default_factory=list)


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
