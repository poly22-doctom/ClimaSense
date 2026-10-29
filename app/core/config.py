"""Configuração da aplicação, lida de variáveis de ambiente / arquivo .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./weather.db"

    station_id: str = "estacao_01"
    station_name: str = "Estação Meteorológica e Ambiental"
    station_location: str = "Localização não configurada"
    timezone: str = "America/Sao_Paulo"

    station_api_key: str = ""
    admin_api_key: str = ""
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    demo_mode: bool = True
    simulation_interval_seconds: int = 300
    simulation_backfill_days: int = 30
    refresh_seconds: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
