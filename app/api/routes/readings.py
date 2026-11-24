import math
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings_dep
from app.core.config import Settings
from app.core.security import require_station_key
from app.core.timeutils import to_naive_utc
from app.repositories import readings as repo
from app.schemas.reading import IngestOut, LatestOut, ReadingIn, ReadingOut, ReadingsPage, SeriesOut
from app.services import readings as svc

router = APIRouter(prefix="/api/readings", tags=["Leituras"])
Period = Literal["24h", "7d", "30d"]
Source = Literal["hardware", "simulated"]


def _station(settings: Settings, station_id: str | None) -> str:
    return station_id or settings.station_id


@router.post("", response_model=IngestOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_station_key)], summary="Recebe uma medição do ESP32 (exige X-API-Key)")
def post_reading(payload: ReadingIn, response: Response, db: Session = Depends(get_db)):
    try:
        reading, created = svc.ingest(db, payload)
    except svc.UnknownStation:
        raise HTTPException(404, "Estação não cadastrada.")
    if not created:
        response.status_code = status.HTTP_200_OK  # reenvio idempotente
    return {"status": "created" if created else "duplicate", "reading": reading}


@router.get("/latest", response_model=LatestOut, summary="Última medição válida")
def latest(station_id: str | None = None, source: Source | None = None, db: Session = Depends(get_db),
           settings: Settings = Depends(get_settings_dep)):
    sid = _station(settings, station_id)
    src = svc.resolve_source(db, settings, sid, source)
    reading = repo.latest_valid(db, sid, src)  # None quando ainda não há dados
    return {"source": src, "reading": reading, "trends": svc.compute_trends(db, sid, src, reading)}


@router.get("/series", response_model=SeriesOut, summary="Série temporal para gráficos (com média por intervalo)")
def series(period: Period = "24h", start: datetime | None = None, end: datetime | None = None,
           station_id: str | None = None, source: Source | None = None,
           max_points: int = Query(300, ge=20, le=1000), db: Session = Depends(get_db),
           settings: Settings = Depends(get_settings_dep)):
    sid = _station(settings, station_id)
    src = svc.resolve_source(db, settings, sid, source)
    pts = svc.series(db, sid, src, period, start, end, max_points)
    return {"source": src, "period": period, "count": len(pts), "points": pts}


@router.get("", response_model=ReadingsPage, summary="Histórico com filtros, ordenação e paginação")
def list_readings(
    period: Period | None = None, start: datetime | None = None, end: datetime | None = None,
    station_id: str | None = None,
    source: Literal["hardware", "simulated", "all"] | None = None,
    sort_by: Literal["timestamp", "temperature_c", "humidity_pct", "pressure_hpa", "mq135_raw", "ldr_raw", "source"] = "timestamp",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep),
):
    if start and end and to_naive_utc(end) < to_naive_utc(start):
        raise HTTPException(422, "A data final deve ser posterior à inicial.")
    sid = _station(settings, station_id)
    src = svc.resolve_source(db, settings, sid, source) if source != "all" else "all"
    s = e = None
    if start or period:
        s, e = svc.period_range(period or "24h", start, end)
    elif end:
        e = to_naive_utc(end)
    items, total = repo.list_readings(db, sid, src, s, e, sort_by, order, (page - 1) * page_size, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size))}
