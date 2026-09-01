from typing import Protocol

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.config import Settings
from app.news_models import (
    ExplainNewsOutput,
    NewsQuestionRequest,
    NewsQuestionResponse,
    NewsQuestionType,
    PeopleMentionedOutput,
)
from app.news_prompts import (
    build_explain_news_prompt,
    build_people_mentioned_prompt,
)


class ResponsesEndpoint(Protocol):
    async def parse(self, **kwargs: object) -> object: ...


class NewsQuestionClient(Protocol):
    responses: ResponsesEndpoint


class NewsQuestionError(Exception):
    """Indica falha segura na geração ou validação da resposta."""


class NewsQuestionService:
    """Seleciona o caso de uso e produz uma resposta estruturada pela OpenAI."""

    def __init__(self, client: NewsQuestionClient, model: str) -> None:
        self._client = client
        self._model = model

    async def answer(
        self,
        request: NewsQuestionRequest,
    ) -> NewsQuestionResponse:
        if request.question_type is NewsQuestionType.EXPLAIN_NEWS:
            prompt = build_explain_news_prompt(request)
            output_type = ExplainNewsOutput
        else:
            prompt = build_people_mentioned_prompt(request)
            output_type = PeopleMentionedOutput

        try:
            response = await self._client.responses.parse(
                model=self._model,
                input=prompt,
                text_format=output_type,
                max_output_tokens=800,
                store=False,
                temperature=0.1,
            )
        except (OpenAIError, ValidationError) as error:
            raise NewsQuestionError("Could not answer news question") from error

        parsed = response.output_parsed  # type: ignore[attr-defined]
        if parsed is None:
            raise NewsQuestionError("OpenAI returned no structured news answer")

        try:
            return NewsQuestionResponse.model_validate(parsed.model_dump())
        except ValidationError as error:
            raise NewsQuestionError(
                "OpenAI returned an invalid structured news answer"
            ) from error


def create_news_question_service(settings: Settings) -> NewsQuestionService:
    """Cria o serviço usando a chave e o modelo já configurados no projeto."""

    if not settings.openai_api_key:
        raise NewsQuestionError("OpenAI is not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    return NewsQuestionService(client, settings.openai_response_model)
