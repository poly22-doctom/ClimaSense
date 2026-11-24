from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.services import simulator
from tests.conftest import ADMIN_KEY, iso, make_settings, payload


# ---------- inicialização, saúde e status ----------
def test_app_starts_and_serves_dashboard(client):
    r = client.get("/")
    assert r.status_code == 200 and "Estação Meteorológica e Ambiental" in r.text
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/docs").status_code == 200  # Swagger


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def test_status_waiting_without_data(client):
    j = client.get("/api/station/status").json()
    assert j["connection"] == "waiting" and j["last_seen"] is None and j["available_sources"] == []


def test_latest_is_null_without_data(client):
    j = client.get("/api/readings/latest").json()
    assert j["reading"] is None and all(v is None for v in j["trends"].values())


def test_unknown_station_status_404(client):
    assert client.get("/api/station/status", params={"station_id": "outra"}).status_code == 404


# ---------- autenticação ----------
def test_post_requires_key(client):
    assert client.post("/api/readings", json=payload()).status_code == 401
    assert client.post("/api/readings", json=payload(), headers={"X-API-Key": "errada"}).status_code == 401


def test_post_disabled_when_key_not_configured(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, station_api_key=""))) as c:
        r = c.post("/api/readings", json=payload(), headers={"X-API-Key": ""})
        assert r.status_code == 503  # nunca fica aberto


# ---------- recepção e validação ----------
def test_valid_reading_is_stored_and_status_online(client, auth):
    r = client.post("/api/readings", json=payload(), headers=auth)
    assert r.status_code == 201 and r.json()["status"] == "created"
    latest = client.get("/api/readings/latest").json()
    assert latest["source"] == "hardware" and latest["reading"]["temperature_c"] == 25.4
    assert client.get("/api/station/status").json()["connection"] == "online"


def test_duplicate_resend_is_idempotent(client, auth):
    body = payload()
    assert client.post("/api/readings", json=body, headers=auth).status_code == 201
    r = client.post("/api/readings", json=body, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "duplicate"
    assert client.get("/api/readings").json()["total"] == 1


import pytest  # noqa: E402


@pytest.mark.parametrize("override", [
    {"temperature_c": 500}, {"humidity_pct": 120}, {"humidity_pct": -1}, {"pressure_hpa": 50},
    {"mq135_raw": 9999}, {"ldr_raw": -5}, {"temperature_c": "quente"}, {"timestamp": "ontem"},
    {"timestamp": "2026-10-24T10:30:00"},  # sem fuso
    {"timestamp": (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")},
    {"source": "simulated"},  # simulação não pode entrar pela API
    {"station_id": "id inválido!"}, {"campo_extra": 1},
    {"temperature_c": None, "humidity_pct": None, "pressure_hpa": None, "mq135_raw": None, "ldr_raw": None},
    {"sensor_errors": ["dht22"]},  # declara falha mas envia valores
])
def test_invalid_payloads_rejected(client, auth, override):
    r = client.post("/api/readings", json=payload(**override), headers=auth)
    assert r.status_code == 422, r.text
    assert client.get("/api/readings").json()["total"] == 0


def test_nan_rejected(client, auth):
    r = client.post("/api/readings", content='{"station_id":"estacao_01","temperature_c":NaN}',
                    headers={**auth, "Content-Type": "application/json"})
    assert r.status_code == 422


def test_unknown_station_rejected(client, auth):
    assert client.post("/api/readings", json=payload(station_id="desconhecida"), headers=auth).status_code == 404


def test_sensor_failure_is_recorded_not_invented(client, auth):
    body = payload(temperature_c=None, humidity_pct=None, sensor_errors=["dht22"])
    assert client.post("/api/readings", json=body, headers=auth).status_code == 201
    rd = client.get("/api/readings/latest").json()["reading"]
    assert rd["temperature_c"] is None and rd["sensor_errors"] == ["dht22"]
    codes = [a["code"] for a in client.get("/api/alerts").json()]
    assert "sensor_failure" in codes


def test_oversized_body_rejected(client, auth):
    r = client.post("/api/readings", content="x" * 20000, headers={**auth, "Content-Type": "application/json"})
    assert r.status_code == 413


# ---------- histórico, filtros, ordenação, paginação ----------
def _fill(client, auth, n=6):
    for i in range(n):
        client.post("/api/readings", json=payload(minutes_ago=i * 60, temperature_c=20 + i), headers=auth)


def test_history_filters_sort_pagination(client, auth):
    _fill(client, auth, 6)
    assert client.get("/api/readings", params={"period": "24h"}).json()["total"] == 6
    start = iso(datetime.now(timezone.utc) - timedelta(minutes=130))
    assert client.get("/api/readings", params={"start": start}).json()["total"] == 3
    j = client.get("/api/readings", params={"sort_by": "temperature_c", "order": "asc", "page_size": 4}).json()
    assert [i["temperature_c"] for i in j["items"]] == [20, 21, 22, 23] and j["pages"] == 2
    p2 = client.get("/api/readings", params={"sort_by": "temperature_c", "order": "asc", "page_size": 4, "page": 2}).json()
    assert len(p2["items"]) == 2
    bad = client.get("/api/readings", params={"start": iso(datetime.now(timezone.utc)),
                                              "end": iso(datetime.now(timezone.utc) - timedelta(days=1))})
    assert bad.status_code == 422
    assert client.get("/api/readings", params={"page_size": 9999}).status_code == 422


def test_period_filter_excludes_old(client, auth):
    client.post("/api/readings", json=payload(minutes_ago=60 * 24 * 3), headers=auth)
    assert client.get("/api/readings", params={"period": "24h"}).json()["total"] == 0
    assert client.get("/api/readings", params={"period": "7d"}).json()["total"] == 1


def test_series_returns_points(client, auth):
    _fill(client, auth, 4)
    j = client.get("/api/readings/series", params={"period": "24h"}).json()
    assert j["count"] == 4 and j["points"][0]["t"].endswith("Z")


# ---------- estatísticas ----------
def test_statistics(client, auth):
    _fill(client, auth, 5)  # temperaturas 20..24
    j = client.get("/api/statistics", params={"period": "24h"}).json()
    t = j["metrics"]["temperature_c"]
    assert j["total_readings"] == 5 and t["min"] == 20 and t["max"] == 24 and t["avg"] == 22
    empty = client.get("/api/statistics", params={"source": "simulated"}).json()
    assert empty["total_readings"] == 0 and empty["metrics"]["temperature_c"]["avg"] is None


# ---------- tendências ----------
def test_trend_needs_enough_data(client, auth):
    client.post("/api/readings", json=payload(), headers=auth)
    assert client.get("/api/readings/latest").json()["trends"]["temperature_c"] is None  # 1 ponto: sem tendência
    for m, t in ((120, 20.0), (60, 22.0)):
        client.post("/api/readings", json=payload(minutes_ago=m, temperature_c=t), headers=auth)
    tr = client.get("/api/readings/latest").json()["trends"]["temperature_c"]
    assert tr["direction"] == "up" and tr["delta"] == 5.4


# ---------- alertas ----------
def test_threshold_alerts_measured(client, auth):
    client.post("/api/readings", json=payload(temperature_c=40, humidity_pct=10), headers=auth)
    alerts = {a["code"]: a for a in client.get("/api/alerts").json()}
    assert alerts["temp_high"]["basis"] == "medido" and alerts["humidity_low"]["basis"] == "medido"


def test_pressure_alert_is_estimated(client, auth):
    for m, p in ((180, 1016.0), (120, 1014.5), (60, 1013.0), (0, 1011.5)):
        client.post("/api/readings", json=payload(minutes_ago=m, pressure_hpa=p), headers=auth)
    a = {x["code"]: x for x in client.get("/api/alerts").json()}
    assert a["pressure_change"]["basis"] == "estimado"


def test_offline_alert(client, auth):
    client.post("/api/readings", json=payload(), headers=auth)
    from app.repositories import readings as repo
    from app.core.timeutils import utcnow
    with client.app.state.session_factory() as db:
        from app.models import Reading
        row = db.query(Reading).first()
        row.received_at = utcnow() - timedelta(minutes=90)
        db.commit()
    assert client.get("/api/station/status").json()["connection"] == "offline"
    assert "offline" in [a["code"] for a in client.get("/api/alerts").json()]


def test_alert_settings_require_admin_key_and_validate(client):
    body = client.get("/api/settings/alerts").json()
    body["temp_max_c"] = 30
    assert client.put("/api/settings/alerts", json=body).status_code == 401
    ok = client.put("/api/settings/alerts", json=body, headers={"X-API-Key": ADMIN_KEY})
    assert ok.status_code == 200 and ok.json()["temp_max_c"] == 30
    body["temp_min_c"], body["temp_max_c"] = 30, 20
    assert client.put("/api/settings/alerts", json=body, headers={"X-API-Key": ADMIN_KEY}).status_code == 422


# ---------- separação real x simulado ----------
def test_simulated_and_real_data_are_separated(tmp_path):
    s = make_settings(tmp_path, demo_mode=False, simulation_backfill_days=2)
    with TestClient(create_app(s)) as c:
        n = simulator.generate_missing(c.app.state.session_factory, s)
        assert n > 400
        assert simulator.generate_missing(c.app.state.session_factory, s) == 0  # idempotente
        st = c.get("/api/station/status").json()
        assert st["is_demo"] is True and st["data_source"] == "simulated" and st["available_sources"] == ["simulated"]
        assert c.get("/api/readings", params={"source": "hardware"}).json()["total"] == 0
        # chegam dados reais: passam a ter prioridade e não se misturam com a simulação
        c.post("/api/readings", json=payload(temperature_c=11.1), headers={"X-API-Key": "chave-de-teste-estacao"})
        st = c.get("/api/station/status").json()
        assert st["is_demo"] is False and set(st["available_sources"]) == {"hardware", "simulated"}
        real = c.get("/api/readings").json()
        assert real["total"] == 1 and real["items"][0]["source"] == "hardware"
        sim = c.get("/api/readings", params={"source": "simulated"}).json()
        assert sim["total"] > 400 and all(i["source"] == "simulated" for i in sim["items"])
        assert c.get("/api/statistics").json()["total_readings"] == 1
        assert c.get("/api/readings/latest").json()["reading"]["temperature_c"] == 11.1


def test_simulation_is_smooth_and_plausible(tmp_path):
    from zoneinfo import ZoneInfo
    tz, t0 = ZoneInfo("America/Sao_Paulo"), datetime(2026, 10, 24, 0, 0)
    prev = simulator.sample(t0, tz)
    for i in range(1, 288):
        cur = simulator.sample(t0 + timedelta(minutes=5 * i), tz)
        assert abs(cur["temperature_c"] - prev["temperature_c"]) < 1.0  # sem saltos aleatórios
        assert 0 <= cur["humidity_pct"] <= 100 and 950 < cur["pressure_hpa"] < 1050
        prev = cur
    assert simulator.sample(datetime(2026, 10, 24, 3, 0), tz)["ldr_raw"] < 300  # madrugada = escuro (UTC 03h = 00h local)


def test_demo_mode_starts_single_task(tmp_path):
    s = make_settings(tmp_path, demo_mode=True, simulation_backfill_days=1)
    with TestClient(create_app(s)) as c:
        assert c.app.state.simulator_task is not None
        assert c.get("/api/station/status").json()["is_demo"] in (True, False)
