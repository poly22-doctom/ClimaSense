from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.reading import UtcDatetime


class StationStatus(BaseModel):
    station_id: str
    name: str
    location: str
    timezone: str
    connection: Literal["online", "offline", "waiting"]
    last_seen: UtcDatetime | None
    minutes_since_last: int | None
    data_source: Literal["hardware", "simulated"]
    is_demo: bool
    available_sources: list[str]
    demo_enabled: bool
    refresh_seconds: int
    latitude: float | None = None
    longitude: float | None = None
    coverage_radius_km: float | None = None


class MetricStats(BaseModel):
    count: int
    min: float | None
    max: float | None
    avg: float | None


class StatisticsOut(BaseModel):
    source: Literal["hardware", "simulated"]
    period: str
    total_readings: int
    first_timestamp: UtcDatetime | None
    last_timestamp: UtcDatetime | None
    metrics: dict[str, MetricStats]


class AlertOut(BaseModel):
    code: str
    severity: Literal["atencao", "informativo"]
    basis: Literal["medido", "estimado"] = Field(description="'medido' = fato observado; 'estimado' = interpretação")
    title: str
    message: str


class AlertSettingsIO(BaseModel):
    temp_min_c: float = Field(ge=-40, le=80)
    temp_max_c: float = Field(ge=-40, le=80)
    humidity_min_pct: float = Field(ge=0, le=100)
    humidity_max_pct: float = Field(ge=0, le=100)
    pressure_change_hpa_3h: float = Field(gt=0, le=50)
    mq135_change_pct: float = Field(gt=0, le=500)
    offline_after_minutes: int = Field(ge=1, le=1440)

    def check_order(self) -> None:
        if self.temp_min_c >= self.temp_max_c or self.humidity_min_pct >= self.humidity_max_pct:
            raise ValueError("O limite mínimo deve ser menor que o máximo.")


class TrendlineOut(BaseModel):
    """Reta de tendência y = a·x + b (mínimos quadrados). x = horas desde `t0` (primeiro registro do período)."""
    n: int = Field(description="Quantidade de pontos usados")
    t0: UtcDatetime = Field(description="Instante em que x = 0")
    span_hours: float
    slope_per_hour: float = Field(description="Coeficiente angular a (unidade da grandeza por hora)")
    intercept: float = Field(description="Coeficiente linear b (valor em x = 0)")
    r2: float | None = Field(description="Coeficiente de determinação; None se os valores forem todos iguais")
    change_in_period: float = Field(description="a · span_hours: variação estimada pela reta no período")
    equation: str


class TrendlinesOut(BaseModel):
    source: Literal["hardware", "simulated"]
    period: str
    metrics: dict[str, TrendlineOut | None]


class LatLon(BaseModel):
    latitude: float
    longitude: float


class StationGeo(LatLon):
    coverage_radius_km: float


class PlanePoint(BaseModel):
    x_km: float = Field(description="Leste (+) / oeste (−) em relação à estação")
    y_km: float = Field(description="Norte (+) / sul (−) em relação à estação")


class LineEquation(BaseModel):
    a: float
    b: float
    c: float
    slope: float | None = Field(description="m em y = m·x; None se a reta for vertical")
    equation: str


class ProximityOut(BaseModel):
    station_id: str
    station: StationGeo
    visitor: LatLon
    visitor_plane: PlanePoint
    distance_km: float = Field(description="Distância euclidiana no plano local: √(x² + y²)")
    distance_haversine_km: float = Field(description="Distância sobre a esfera, só para conferência")
    azimuth_deg: float | None = Field(description="0° = norte, 90° = leste; None se estiver sobre a estação")
    direction: str | None
    inside_coverage: bool
    circle_equation: str
    line: LineEquation | None
