"""Configurações centralizadas carregadas do ambiente."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores de execução validados pelo Pydantic Settings."""

    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://localhost/mythra"
    )
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="MYTHRA_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Retorna uma instância reutilizável das configurações."""
    return Settings()
