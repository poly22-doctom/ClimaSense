"""Geolocalização: posição do visitante em relação à estação (geometria analítica no plano local)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.schemas.misc import ProximityOut
from app.services import readings as svc

router = APIRouter(prefix="/api/geo", tags=["Geolocalização"])


@router.get(
    "/proximity", response_model=ProximityOut,
    summary="Distância, direção e área de cobertura entre um ponto (lat, lon) e a estação",
)
def proximity(
    lat: float = Query(..., ge=-90, le=90, description="Latitude do visitante, em graus decimais"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude do visitante, em graus decimais"),
    station_id: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
):
    # A posição do visitante é só usada no cálculo: não é gravada em lugar nenhum.
    try:
        return svc.proximity(db, settings, station_id or settings.station_id, lat, lon)
    except svc.UnknownStation:
        raise HTTPException(404, "Estação não cadastrada.")
    except svc.StationWithoutCoordinates:
        raise HTTPException(409, "A estação ainda não tem coordenadas. Defina STATION_LATITUDE e STATION_LONGITUDE no .env.")
