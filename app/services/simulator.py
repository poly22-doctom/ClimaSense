"""Gerador de dados SIMULADOS (modo demonstração).

As séries são funções suaves e determinísticas do instante (ciclo diário + oscilações lentas),
portanto coerentes entre si e entre reinicializações. Tudo é gravado com source="simulated"
e nunca toca em registros reais (a chave única inclui a origem)."""
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.timeutils import utcnow
from app.models import Reading
from app.repositories import readings as repo

log = logging.getLogger("simulador")
TAU = 2 * math.pi


def _slow(t_h: float, seed: float) -> float:
    """Oscilação lenta e suave em [-1, 1] (soma de senoides com períodos diferentes)."""
    return (math.sin(TAU * t_h / 37 + seed) + 0.6 * math.sin(TAU * t_h / 71 + 2 * seed)
            + 0.4 * math.sin(TAU * t_h / 13 + 3 * seed)) / 2.0


def sample(ts_utc: datetime, tz: ZoneInfo) -> dict:
    t_h = ts_utc.replace(tzinfo=timezone.utc).timestamp() / 3600
    local = ts_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    h = local.hour + local.minute / 60

    temp = 23 + 4.5 * math.sin(TAU * (h - 9) / 24) + 2.5 * _slow(t_h, 1.1)  # máximo ~15 h
    hum = 65 - 1.8 * (temp - 23) + 6 * _slow(t_h, 2.3)  # umidade cai quando esquenta
    press = 1013 + 4 * math.sin(TAU * t_h / (24 * 3.3) + 0.5) + 2 * _slow(t_h, 3.7) + 0.8 * math.sin(TAU * h / 12)
    pulse = 380 * max(0.0, math.sin(TAU * t_h / 61)) ** 12  # picos curtos e raros
    mq = 1750 + 120 * math.sin(TAU * (h - 8) / 24) + 80 * _slow(t_h, 4.9) + pulse
    daylight = max(0.0, math.sin(math.pi * (h - 6) / 12)) if 6 <= h <= 18 else 0.0
    cloud = 0.65 + 0.35 * (_slow(t_h, 5.3) + 1) / 2
    ldr = 120 + 3800 * daylight * cloud

    return {
        "temperature_c": round(min(max(temp, -40), 80), 1),
        "humidity_pct": round(min(max(hum, 25), 98), 1),
        "pressure_hpa": round(press, 1),
        "bmp280_temperature_c": round(temp + 0.6, 1),  # sensor auxiliar, próprio da placa
        "mq135_raw": int(min(max(mq, 0), 4095)),
        "ldr_raw": int(min(max(ldr, 0), 4095)),
    }


def generate_missing(session_factory: sessionmaker[Session], settings: Settings, now: datetime | None = None) -> int:
    """Preenche as lacunas de dados simulados até o instante atual. Idempotente."""
    now = now or utcnow()
    step = max(settings.simulation_interval_seconds, 60)
    tz = ZoneInfo(settings.timezone)
    epoch = int(now.replace(tzinfo=timezone.utc).timestamp())
    end = datetime.fromtimestamp(epoch - epoch % step, tz=timezone.utc).replace(tzinfo=None)
    earliest = end - timedelta(days=settings.simulation_backfill_days)
    inserted = 0
    with session_factory() as db:
        last = repo.last_simulated_timestamp(db, settings.station_id)
        cur = earliest if last is None else max(last + timedelta(seconds=step), earliest)
        cur_epoch = int(cur.replace(tzinfo=timezone.utc).timestamp())
        cur = datetime.fromtimestamp(cur_epoch - cur_epoch % step, tz=timezone.utc).replace(tzinfo=None)
        batch: list[dict] = []
        while cur <= end:
            batch.append({"station_id": settings.station_id, "timestamp": cur, "received_at": cur,
                          "source": "simulated", "sensor_errors": "", **sample(cur, tz)})
            cur += timedelta(seconds=step)
            if len(batch) >= 2000:
                db.execute(insert(Reading), batch); db.commit(); inserted += len(batch); batch = []
        if batch:
            db.execute(insert(Reading), batch); db.commit(); inserted += len(batch)
    return inserted


async def run_simulator(session_factory: sessionmaker[Session], settings: Settings) -> None:
    """Tarefa única de fundo (criada uma vez no startup)."""
    interval = max(settings.simulation_interval_seconds, 60)
    while True:
        try:
            n = await asyncio.to_thread(generate_missing, session_factory, settings)
            if n:
                log.info("Simulador: %d leitura(s) simulada(s) gravada(s).", n)
        except Exception:  # não derruba o servidor
            log.exception("Falha no simulador de dados")
        await asyncio.sleep(interval)
