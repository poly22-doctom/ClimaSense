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
