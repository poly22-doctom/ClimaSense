"""Estatísticas, alertas e limites de alerta."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.core.security import require_admin_key
from app.repositories import readings as repo
from app.schemas.misc import AlertOut, AlertSettingsIO, StatisticsOut
from app.services import alerts as alert_svc
from app.services import readings as svc

router = APIRouter(prefix="/api", tags=["Análise"])


@router.get("/statistics", response_model=StatisticsOut, summary="Estatísticas dos registros do período")
def statistics(period: Literal["24h", "7d", "30d"] = "24h", start: datetime | None = None, end: datetime | None = None,
               station_id: str | None = None, source: Literal["hardware", "simulated"] | None = None,
               db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    sid = station_id or settings.station_id
    return svc.statistics(db, sid, svc.resolve_source(db, settings, sid, source), period, start, end)


@router.get("/alerts", response_model=list[AlertOut], summary="Alertas ativos (medidos x estimados)")
def alerts(station_id: str | None = None, source: Literal["hardware", "simulated"] | None = None,
           db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    sid = station_id or settings.station_id
    return alert_svc.evaluate(db, sid, svc.resolve_source(db, settings, sid, source))


@router.get("/settings/alerts", response_model=AlertSettingsIO, summary="Limites de alerta configurados")
def get_alert_settings(station_id: str | None = None, db: Session = Depends(get_db),
                       settings: Settings = Depends(get_settings_dep)):
    return repo.get_alert_settings(db, station_id or settings.station_id)


@router.put("/settings/alerts", response_model=AlertSettingsIO, dependencies=[Depends(require_admin_key)],
            summary="Altera os limites de alerta (exige X-API-Key de administrador)")
def put_alert_settings(body: AlertSettingsIO, station_id: str | None = None, db: Session = Depends(get_db),
                       settings: Settings = Depends(get_settings_dep)):
    try:
        body.check_order()
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    row = repo.get_alert_settings(db, station_id or settings.station_id)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    return row
