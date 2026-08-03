from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def require_internal_secret(
    internal_secret: Annotated[str | None, Header(alias="X-Internal-Secret")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """Interrompe requisições que não apresentam o segredo interno correto."""

    secret_is_valid = (
        bool(settings.internal_api_secret)
        and internal_secret is not None
        and compare_digest(internal_secret, settings.internal_api_secret)
    )
    if not secret_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal secret",
        )
