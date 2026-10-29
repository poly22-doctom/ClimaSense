"""Acesso ao banco: somente consultas/gravações, sem regras de negócio."""
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AlertSettings, Reading, Station

MEASURE_COLS = ("temperature_c", "humidity_pct", "pressure_hpa", "mq135_raw", "ldr_raw")
SORTABLE = {"timestamp", "temperature_c", "humidity_pct", "pressure_hpa", "mq135_raw", "ldr_raw", "source"}


def _base(station_id: str, source: str | None, start: datetime | None, end: datetime | None):
    conds = [Reading.station_id == station_id]
    if source and source != "all":
        conds.append(Reading.source == source)
    if start:
        conds.append(Reading.timestamp >= start)
    if end:
        conds.append(Reading.timestamp <= end)
    return conds


def get_station(db: Session, station_id: str) -> Station | None:
    return db.scalar(select(Station).where(Station.station_id == station_id))


def upsert_station(db: Session, station_id: str, name: str, location: str) -> Station:
    st = get_station(db, station_id)
    if st is None:
        st = Station(station_id=station_id, name=name, location=location)
        db.add(st)
    else:
        st.name, st.location = name, location
    db.commit()
    return st


def get_alert_settings(db: Session, station_id: str) -> AlertSettings:
    row = db.scalar(select(AlertSettings).where(AlertSettings.station_id == station_id))
    if row is None:
        row = AlertSettings(station_id=station_id)
        db.add(row)
        db.commit()
    return row


def create_reading(db: Session, **values) -> tuple[Reading, bool]:
    """Insere a leitura; se (estação, instante, origem) já existir devolve a existente."""
    existing = db.scalar(
        select(Reading).where(
            Reading.station_id == values["station_id"],
            Reading.timestamp == values["timestamp"],
            Reading.source == values["source"],
        )
    )
    if existing:
        return existing, False
    obj = Reading(**values)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:  # corrida entre dois reenvios simultâneos
        db.rollback()
        existing = db.scalar(
            select(Reading).where(
                Reading.station_id == values["station_id"],
                Reading.timestamp == values["timestamp"],
                Reading.source == values["source"],
            )
        )
        if existing:
            return existing, False
        raise
    return obj, True


def count_by_source(db: Session, station_id: str) -> dict[str, int]:
    rows = db.execute(
        select(Reading.source, func.count()).where(Reading.station_id == station_id).group_by(Reading.source)
    ).all()
    return {s: c for s, c in rows}


def latest_valid(db: Session, station_id: str, source: str) -> Reading | None:
    has_value = or_(*(getattr(Reading, c).is_not(None) for c in MEASURE_COLS))
    return db.scalar(
        select(Reading)
        .where(*_base(station_id, source, None, None), has_value)
        .order_by(Reading.timestamp.desc())
        .limit(1)
    )


def latest_any(db: Session, station_id: str, source: str) -> Reading | None:
    return db.scalar(
        select(Reading).where(*_base(station_id, source, None, None)).order_by(Reading.timestamp.desc()).limit(1)
    )


def last_received_at(db: Session, station_id: str, source: str) -> datetime | None:
    return db.scalar(select(func.max(Reading.received_at)).where(*_base(station_id, source, None, None)))


def last_simulated_timestamp(db: Session, station_id: str) -> datetime | None:
    return db.scalar(
        select(func.max(Reading.timestamp)).where(Reading.station_id == station_id, Reading.source == "simulated")
    )


def list_readings(
    db: Session, station_id: str, source: str | None, start, end, sort_by: str, order: str, offset: int, limit: int
) -> tuple[list[Reading], int]:
    conds = _base(station_id, source, start, end)
    total = db.scalar(select(func.count()).select_from(Reading).where(*conds)) or 0
    col = getattr(Reading, sort_by if sort_by in SORTABLE else "timestamp")
    ordering = col.asc() if order == "asc" else col.desc()
    rows = db.scalars(
        select(Reading).where(*conds).order_by(ordering, Reading.id.desc()).offset(offset).limit(limit)
    ).all()
    return list(rows), total


def rows_in_range(db: Session, station_id: str, source: str, start, end) -> list[tuple]:
    cols = [Reading.timestamp] + [getattr(Reading, c) for c in MEASURE_COLS]
    return list(db.execute(select(*cols).where(*_base(station_id, source, start, end)).order_by(Reading.timestamp)).all())


def aggregate(db: Session, station_id: str, source: str, start, end) -> dict:
    exprs = [func.count().label("total"), func.min(Reading.timestamp).label("first"), func.max(Reading.timestamp).label("last")]
    for c in MEASURE_COLS:
        col = getattr(Reading, c)
        exprs += [func.count(col).label(f"{c}_n"), func.min(col).label(f"{c}_min"),
                  func.max(col).label(f"{c}_max"), func.avg(col).label(f"{c}_avg")]
    return dict(db.execute(select(*exprs).where(*_base(station_id, source, start, end))).one()._mapping)
