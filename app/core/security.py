"""Autenticação por chave de API em cabeçalho (X-API-Key)."""
import hmac

from fastapi import Depends, Header, HTTPException, status

from app.api.deps import get_settings_dep
from app.core.config import Settings


def _check(provided: str | None, expected: str, nome: str) -> None:
    if not expected:
        # Sem chave configurada o endpoint de escrita permanece desativado (nunca aberto).
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{nome} não configurada no servidor. Defina a variável de ambiente correspondente.",
        )
    if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Chave de API ausente ou inválida.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def require_station_key(
    x_api_key: str | None = Header(default=None), settings: Settings = Depends(get_settings_dep)
) -> None:
    _check(x_api_key, settings.station_api_key, "STATION_API_KEY")


def require_admin_key(
    x_api_key: str | None = Header(default=None), settings: Settings = Depends(get_settings_dep)
) -> None:
    _check(x_api_key, settings.admin_api_key, "ADMIN_API_KEY")
