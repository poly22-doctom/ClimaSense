"""Regras de negócio: ingestão, séries, tendências, estatísticas e estado da estação."""
import math
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.timeutils import to_naive_utc, utcnow
from app.models.reading import SOURCE_HARDWARE, SOURCE_SIMULATED
from app.repositories import readings as repo
from app.schemas.reading import ReadingIn

PERIODS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
# Variação mínima para considerar "subindo/descendo" (abaixo disso = estável)
TREND_THRESHOLD = {"temperature_c": 0.3, "humidity_pct": 2.0, "pressure_hpa": 0.5, "mq135_raw": 40.0, "ldr_raw": 150.0}


class UnknownStation(Exception):
    pass


def period_range(period: str, start: datetime | None, end: datetime | None) -> tuple[datetime, datetime | None]:
    """Intervalo explícito (start/end) tem prioridade sobre o atalho `period`."""
    if start is not None:
        return to_naive_utc(start), to_naive_utc(end) if end else None
    return utcnow() - PERIODS[period], None


def resolve_source(db: Session, settings: Settings, station_id: str, requested: str | None) -> str:
    """Sem `source` explícito: dados reais se existirem; senão demonstração (se houver)."""
    if requested in (SOURCE_HARDWARE, SOURCE_SIMULATED):
        return requested
    counts = repo.count_by_source(db, station_id)
    if counts.get(SOURCE_HARDWARE):
        return SOURCE_HARDWARE
    if counts.get(SOURCE_SIMULATED):
        return SOURCE_SIMULATED
    return SOURCE_HARDWARE


def ingest(db: Session, payload: ReadingIn):
    if repo.get_station(db, payload.station_id) is None:
        raise UnknownStation(payload.station_id)
    ts = to_naive_utc(payload.timestamp) if payload.timestamp else utcnow().replace(microsecond=0)
    return repo.create_reading(
        db,
        station_id=payload.station_id,
        timestamp=ts,
        received_at=utcnow(),
        source=SOURCE_HARDWARE,
        temperature_c=payload.temperature_c,
        humidity_pct=payload.humidity_pct,
        pressure_hpa=payload.pressure_hpa,
        bmp280_temperature_c=payload.bmp280_temperature_c,
        mq135_raw=payload.mq135_raw,
        ldr_raw=payload.ldr_raw,
        sensor_errors=",".join(sorted(set(payload.sensor_errors))),
    )


def compute_trends(db: Session, station_id: str, source: str, latest) -> dict:
    """Tendência = variação entre a primeira e a última leitura das últimas 3 h.
    Só é calculada com >= 3 pontos e janela >= 30 min; senão devolve None (nunca inventa)."""
    out: dict = {c: None for c in repo.MEASURE_COLS}
    if latest is None:
        return out
    rows = repo.rows_in_range(db, station_id, source, latest.timestamp - timedelta(hours=3), latest.timestamp)
    for i, col in enumerate(repo.MEASURE_COLS, start=1):
        pts = [(r[0], r[i]) for r in rows if r[i] is not None]
        if len(pts) < 3:
            continue
        span = (pts[-1][0] - pts[0][0]).total_seconds() / 60
        if span < 30:
            continue
        delta = pts[-1][1] - pts[0][1]
        thr = TREND_THRESHOLD[col]
        direction = "flat" if abs(delta) < thr else ("up" if delta > 0 else "down")
        out[col] = {"direction": direction, "delta": round(delta, 2), "window_minutes": int(round(span))}
    return out


def series(db: Session, station_id: str, source: str, period: str, start, end, max_points: int) -> list[dict]:
    """Série para gráficos; se houver mais pontos que `max_points`, faz média por intervalo."""
    s, e = period_range(period, start, end)
    rows = repo.rows_in_range(db, station_id, source, s, e)
    cols = repo.MEASURE_COLS
    if len(rows) <= max_points:
        return [{"t": r[0], **{c: r[i] for i, c in enumerate(cols, start=1)}} for r in rows]
    t0 = rows[0][0]
    span = max((rows[-1][0] - t0).total_seconds(), 1)
    bucket = math.ceil(span / max_points)
    buckets: dict[int, list[tuple]] = {}
    for r in rows:
        buckets.setdefault(int((r[0] - t0).total_seconds() // bucket), []).append(r)
    result = []
    for k in sorted(buckets):
        grp = buckets[k]
        point = {"t": t0 + timedelta(seconds=k * bucket + bucket // 2)}
        for i, c in enumerate(cols, start=1):
            vals = [g[i] for g in grp if g[i] is not None]
            point[c] = round(sum(vals) / len(vals), 2) if vals else None
        result.append(point)
    return result


def statistics(db: Session, station_id: str, source: str, period: str, start, end) -> dict:
    s, e = period_range(period, start, end)
    agg = repo.aggregate(db, station_id, source, s, e)
    metrics = {}
    for c in repo.MEASURE_COLS:
        avg = agg[f"{c}_avg"]
        metrics[c] = {
            "count": agg[f"{c}_n"],
            "min": agg[f"{c}_min"],
            "max": agg[f"{c}_max"],
            "avg": round(avg, 2) if avg is not None else None,
        }
    return {
        "source": source, "period": period, "total_readings": agg["total"],
        "first_timestamp": agg["first"], "last_timestamp": agg["last"], "metrics": metrics,
    }


def station_status(db: Session, settings: Settings, station_id: str, source: str | None) -> dict:
    st = repo.get_station(db, station_id)
    if st is None:
        raise UnknownStation(station_id)
    src = resolve_source(db, settings, station_id, source)
    cfg = repo.get_alert_settings(db, station_id)
    last = repo.last_received_at(db, station_id, src)
    latest = repo.latest_any(db, station_id, src)
    minutes = None
    if last is None:
        connection = "waiting"
    else:
        minutes = int((utcnow() - last).total_seconds() // 60)
        connection = "online" if minutes <= cfg.offline_after_minutes else "offline"
    counts = repo.count_by_source(db, station_id)
    return {
        "station_id": st.station_id, "name": st.name, "location": st.location, "timezone": settings.timezone,
        "connection": connection, "last_seen": latest.timestamp if latest else None,
        "minutes_since_last": minutes, "data_source": src, "is_demo": src == SOURCE_SIMULATED,
        "available_sources": [s for s in (SOURCE_HARDWARE, SOURCE_SIMULATED) if counts.get(s)],
        "demo_enabled": settings.demo_mode, "refresh_seconds": settings.refresh_seconds,
    }
