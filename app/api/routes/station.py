from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.schemas.misc import StationStatus
from app.services import readings as svc

router = APIRouter(prefix="/api/station", tags=["Estação"])


@router.get("/status", response_model=StationStatus, summary="Estado da estação e última comunicação")
def station_status(
    station_id: str | None = None,
    source: Literal["hardware", "simulated"] | None = Query(None, description="Omitido = reais se existirem, senão demonstração"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
):
    try:
        return svc.station_status(db, settings, station_id or settings.station_id, source)
    except svc.UnknownStation:
        raise HTTPException(404, "Estação não cadastrada.")
