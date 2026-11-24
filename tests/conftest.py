from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

STATION_KEY = "chave-de-teste-estacao"
ADMIN_KEY = "chave-de-teste-admin"


def make_settings(tmp_path, **over) -> Settings:
    base = dict(
        _env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}", station_id="estacao_01",
        station_api_key=STATION_KEY, admin_api_key=ADMIN_KEY, demo_mode=False,
        cors_origins="http://localhost:8000",
    )
    base.update(over)
    return Settings(**base)


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as c:
        yield c


@pytest.fixture()
def auth():
    return {"X-API-Key": STATION_KEY}


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload(minutes_ago: float = 0, **over) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    body = {"station_id": "estacao_01", "timestamp": iso(ts), "temperature_c": 25.4, "humidity_pct": 67.2,
            "pressure_hpa": 1012.8, "mq135_raw": 1840, "ldr_raw": 2150, "source": "hardware"}
    body.update(over)
    return body
