from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação carregada de variáveis de ambiente."""

    supabase_url: str = Field(min_length=1)
    supabase_service_role_key: str = Field(min_length=1, repr=False)
    openai_api_key: str = Field(min_length=1, repr=False)
    internal_api_secret: str = Field(min_length=16, repr=False)
    openai_embedding_model: str = "text-embedding-3-small"
    openai_response_model: str = "gpt-4.1-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cria uma única instância de configuração por processo."""

    return Settings()
