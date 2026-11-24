"""Geometria analítica, geolocalização, reta de tendência e migração de colunas."""
import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.database.connection import init_db
from app.main import create_app
from app.services import geometry
from tests.conftest import make_settings, payload

LAT, LON = -23.5505, -46.6333  # ponto de exemplo
DEG_KM = geometry.EARTH_RADIUS_KM * math.pi / 180  # 1° de latitude ≈ 111,19 km


@pytest.fixture()
def geo_client(tmp_path):
    s = make_settings(tmp_path, station_latitude=LAT, station_longitude=LON, station_coverage_km=5.0)
    with TestClient(create_app(s)) as c:
        yield c


# ---------- funções puras ----------
def test_distance_is_pythagoras():
    assert geometry.distance((0, 0), (3, 4)) == 5
    assert geometry.distance((1, 1), (1, 1)) == 0


def test_inside_circle_uses_squares_and_includes_border():
    assert geometry.inside_circle((3, 4), (0, 0), 5)      # sobre a circunferência
    assert not geometry.inside_circle((3, 4.01), (0, 0), 5)


def test_azimuth_and_compass():
    assert geometry.azimuth_deg((0, 1)) == pytest.approx(0)       # norte
    assert geometry.azimuth_deg((1, 0)) == pytest.approx(90)      # leste
    assert geometry.azimuth_deg((0, -1)) == pytest.approx(180)    # sul
    assert geometry.azimuth_deg((-1, 0)) == pytest.approx(270)    # oeste
    assert geometry.azimuth_deg((0, 0)) is None
    assert [geometry.compass(a) for a in (0, 45, 90, 225, 315, 359)] == ["N", "NE", "L", "SO", "NO", "N"]


def test_line_through_origin():
    ln = geometry.line_through_origin((2, 4))
    assert ln["slope"] == 2 and not ln["vertical"] and ln["a"] * 2 + ln["b"] * 4 == 0  # a·x + b·y = 0 passa por P
    assert geometry.line_through_origin((0, 5))["vertical"]
    assert geometry.line_through_origin((0, 0)) is None


def test_linear_regression_perfect_line():
    f = geometry.linear_regression([0, 1, 2, 3], [1, 3, 5, 7])  # y = 2x + 1
    assert f["slope"] == pytest.approx(2) and f["intercept"] == pytest.approx(1) and f["r2"] == pytest.approx(1)


def test_linear_regression_degenerate_cases():
    assert geometry.linear_regression([1, 1, 1], [1, 2, 3]) is None  # x constante: sem reta única
    assert geometry.linear_regression([1], [1]) is None
    flat = geometry.linear_regression([0, 1, 2], [5, 5, 5])
    assert flat["slope"] == pytest.approx(0) and flat["r2"] is None


def test_projection_matches_haversine_for_short_distances():
    p = geometry.project_km(LAT + 0.05, LON + 0.05, LAT, LON)
    plane = geometry.distance((0, 0), p)
    sphere = geometry.haversine_km(LAT, LON, LAT + 0.05, LON + 0.05)
    assert abs(plane - sphere) / sphere < 0.005  # menos de 0,5 % de diferença


# ---------- API de proximidade ----------
def test_status_exposes_coordinates(geo_client):
    j = geo_client.get("/api/station/status").json()
    assert (j["latitude"], j["longitude"], j["coverage_radius_km"]) == (LAT, LON, 5.0)


def test_status_without_coordinates_is_null(client):
    j = client.get("/api/station/status").json()
    assert j["latitude"] is None and j["coverage_radius_km"] is None


def test_proximity_north_inside_coverage(geo_client):
    r = geo_client.get("/api/geo/proximity", params={"lat": LAT + 0.01, "lon": LON})
    assert r.status_code == 200
    j = r.json()
    assert j["distance_km"] == pytest.approx(0.01 * DEG_KM, rel=1e-6)
    assert j["azimuth_deg"] == pytest.approx(0, abs=1e-6) and j["direction"] == "N"
    assert j["inside_coverage"] is True
    assert j["line"]["slope"] is None and j["line"]["equation"] == "x = 0"  # ao norte da estação: reta vertical


def test_proximity_east_outside_coverage(geo_client):
    j = geo_client.get("/api/geo/proximity", params={"lat": LAT, "lon": LON + 0.2}).json()
    assert j["direction"] == "L" and j["azimuth_deg"] == pytest.approx(90, abs=1e-6)
    assert j["inside_coverage"] is False and j["distance_km"] > 5
    assert "x² + y² = 25" in j["circle_equation"]
    assert j["line"]["slope"] == pytest.approx(0, abs=1e-6) and j["line"]["equation"].startswith("y = ")  # horizontal


def test_proximity_on_station_has_no_direction(geo_client):
    j = geo_client.get("/api/geo/proximity", params={"lat": LAT, "lon": LON}).json()
    assert j["distance_km"] == 0 and j["azimuth_deg"] is None and j["line"] is None and j["inside_coverage"] is True


@pytest.mark.parametrize("params", [{"lat": 91, "lon": 0}, {"lat": 0, "lon": 181}, {"lat": "abc", "lon": 0}, {"lat": 0}])
def test_proximity_rejects_invalid_coordinates(geo_client, params):
    assert geo_client.get("/api/geo/proximity", params=params).status_code == 422


def test_proximity_409_when_station_has_no_coordinates(client):
    assert client.get("/api/geo/proximity", params={"lat": 0, "lon": 0}).status_code == 409


def test_proximity_unknown_station_404(geo_client):
    assert geo_client.get("/api/geo/proximity", params={"lat": 0, "lon": 0, "station_id": "x"}).status_code == 404


# ---------- reta de tendência ----------
def test_trendline_recovers_one_degree_per_hour(client, auth):
    for minutes_ago, temp in ((180, 20.0), (120, 21.0), (60, 22.0), (0, 23.0)):
        assert client.post("/api/readings", json=payload(minutes_ago, temperature_c=temp), headers=auth).status_code == 201
    j = client.get("/api/trendline", params={"period": "24h", "source": "hardware"}).json()
    t = j["metrics"]["temperature_c"]
    assert t["n"] == 4 and t["slope_per_hour"] == pytest.approx(1.0, abs=0.02)
    assert t["r2"] == pytest.approx(1.0, abs=1e-3) and t["change_in_period"] == pytest.approx(3.0, abs=0.05)
    assert t["equation"].startswith("y = 1.0")


def test_trendline_needs_enough_points(client, auth):
    client.post("/api/readings", json=payload(60), headers=auth)
    client.post("/api/readings", json=payload(0, ), headers=auth)
    j = client.get("/api/trendline", params={"source": "hardware"}).json()
    assert all(v is None for v in j["metrics"].values())


# ---------- migração de bancos antigos ----------
def test_init_db_adds_geo_columns_to_old_stations_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE stations (id INTEGER PRIMARY KEY, station_id VARCHAR(64) UNIQUE, "
                       "name VARCHAR(120), location VARCHAR(200), created_at DATETIME)"))
        c.execute(text("INSERT INTO stations (station_id, name, location) VALUES ('estacao_01', 'Antiga', 'X')"))
    init_db(engine)
    init_db(engine)  # idempotente
    cols = {c["name"] for c in inspect(engine).get_columns("stations")}
    assert {"latitude", "longitude", "coverage_radius_km"} <= cols
    with engine.connect() as c:
        assert c.execute(text("SELECT name FROM stations")).scalar() == "Antiga"  # dados preservados
