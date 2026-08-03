from typing import Annotated

from fastapi import Depends, HTTPException, status
from supabase import Client, create_client

from app.config import Settings, get_settings


def get_supabase_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Client:
    """Cria o cliente servidor-servidor usado para acessar o Supabase."""

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase is not configured",
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
