from typing import Protocol

from openai import APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.config import Settings
from app.legislative_models import (
    LegislativeVoteExplanationRequest,
    LegislativeVoteExplanationResponse,
)
from app.legislative_prompts import (
    EXPLANATION_VERSION,
    build_legislative_vote_prompt,
)


UNKNOWN_RESULT_LIMITATION = (
    "O código do resultado não possui um mapeamento oficial fornecido, por isso "
    "seu significado não pode ser interpretado."
)
MISSING_RESULT_LIMITATION = (
    "Os dados fornecidos não informam o resultado coletivo da votação."
)
SECRET_VOTE_LIMITATION = (
    "Por ser uma votação secreta, estes dados não permitem atribuir votos ou "
    "preferências individuais."
)


class ResponsesEndpoint(Protocol):
    async def parse(self, **kwargs: object) -> object: ...


class LegislativeExplanationClient(Protocol):
    responses: ResponsesEndpoint


class LegislativeExplanationError(Exception):
    """Indica falha segura ao gerar ou validar a explicação."""


class LegislativeExplanationTimeoutError(LegislativeExplanationError):
    """Indica que a OpenAI excedeu o limite de tempo configurado."""


class LegislativeVoteExplanationService:
    """Gera uma explicação estruturada sem acessar persistência externa."""

    def __init__(self, client: LegislativeExplanationClient, model: str) -> None:
        self._client = client
        self._model = model

    async def explain(
        self,
        request: LegislativeVoteExplanationRequest,
    ) -> LegislativeVoteExplanationResponse:
        try:
            response = await self._client.responses.parse(
                model=self._model,
                input=build_legislative_vote_prompt(request),
                text_format=LegislativeVoteExplanationResponse,
                max_output_tokens=1_200,
                store=False,
                temperature=0,
            )
        except APITimeoutError as error:
            raise LegislativeExplanationTimeoutError(
                "OpenAI timed out while explaining the legislative vote"
            ) from error
        except (OpenAIError, ValidationError) as error:
            raise LegislativeExplanationError(
                "Could not explain legislative vote"
            ) from error

        parsed = response.output_parsed  # type: ignore[attr-defined]
        if parsed is None:
            raise LegislativeExplanationError(
                "OpenAI returned no structured legislative explanation"
            )

        try:
            result = LegislativeVoteExplanationResponse.model_validate(
                parsed.model_dump()
            )
        except ValidationError as error:
            raise LegislativeExplanationError(
                "OpenAI returned an invalid legislative explanation"
            ) from error

        result.explanation_version = EXPLANATION_VERSION
        result.limitations = _required_limitations(request, result.limitations)

        if _has_unknown_result_code(request):
            code = request.original_result.code  # type: ignore[union-attr]
            result.result_explanation = (
                f'Os dados oficiais informam o código de resultado "{code}", '
                "mas não fornecem um mapeamento validado para explicar seu significado."
            )
        elif request.original_result is None:
            result.result_explanation = MISSING_RESULT_LIMITATION

        return result


def _has_unknown_result_code(
    request: LegislativeVoteExplanationRequest,
) -> bool:
    result = request.original_result
    if result is None or not result.code or result.description:
        return False
    return result.code not in request.official_result_code_mappings


def _required_limitations(
    request: LegislativeVoteExplanationRequest,
    generated: list[str],
) -> list[str]:
    limitations = list(generated)
    if request.original_result is None:
        limitations.append(MISSING_RESULT_LIMITATION)
    elif _has_unknown_result_code(request):
        limitations.append(UNKNOWN_RESULT_LIMITATION)
    if request.secret is True:
        limitations.append(SECRET_VOTE_LIMITATION)
    return list(dict.fromkeys(limitations))[:12]


def create_legislative_explanation_service(
    settings: Settings,
) -> LegislativeVoteExplanationService:
    """Cria o cliente com timeout explícito e sem dependência de banco."""

    if not settings.openai_api_key:
        raise LegislativeExplanationError("OpenAI is not configured")

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_legislative_timeout_seconds,
    )
    return LegislativeVoteExplanationService(
        client,
        settings.openai_response_model,
    )
