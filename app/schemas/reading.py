"""Contrato JSON de leituras. Todas as validações do payload do ESP32 ficam aqui."""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from app.core.timeutils import iso_z

UtcDatetime = Annotated[datetime, PlainSerializer(lambda d: iso_z(d), return_type=str, when_used="json")]

SensorName = Literal["dht22", "bmp280", "mq135", "ldr"]
_MEASURES = ("temperature_c", "humidity_pct", "pressure_hpa", "bmp280_temperature_c", "mq135_raw", "ldr_raw")
# Quais campos pertencem a qual sensor (usado para detectar contradições no payload)
_SENSOR_FIELDS = {
    "dht22": ("temperature_c", "humidity_pct"),
    "bmp280": ("pressure_hpa", "bmp280_temperature_c"),
    "mq135": ("mq135_raw",),
    "ldr": ("ldr_raw",),
}


class ReadingIn(BaseModel):
    """Payload enviado pelo ESP32. Campos de sensor são opcionais: sensor com falha = omitido/null."""

    model_config = ConfigDict(extra="forbid")

    station_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    timestamp: datetime | None = Field(
        default=None, description="ISO 8601 com fuso (ex.: 2026-10-24T10:30:00Z). Se omitido, usa a hora do servidor."
    )
    temperature_c: float | None = Field(default=None, ge=-40, le=80, allow_inf_nan=False)
    humidity_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    pressure_hpa: float | None = Field(default=None, ge=300, le=1100, allow_inf_nan=False)
    bmp280_temperature_c: float | None = Field(default=None, ge=-40, le=85, allow_inf_nan=False)
    mq135_raw: int | None = Field(default=None, ge=0, le=4095)
    ldr_raw: int | None = Field(default=None, ge=0, le=4095)
    source: Literal["hardware"] = Field(default="hardware", description="Somente 'hardware' é aceito pela API.")
    sensor_errors: list[SensorName] = Field(default_factory=list, max_length=4)

    @field_validator("timestamp")
    @classmethod
    def _valid_timestamp(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("timestamp deve incluir o fuso horário (ex.: sufixo 'Z').")
        now = datetime.now(timezone.utc)
        if v > now + timedelta(minutes=5):
            raise ValueError("timestamp está no futuro.")
        if v < now - timedelta(days=365):
            raise ValueError("timestamp é antigo demais (mais de 1 ano).")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> "ReadingIn":
        has_measure = any(getattr(self, f) is not None for f in _MEASURES)
        if not has_measure and not self.sensor_errors:
            raise ValueError("Informe ao menos uma medição ou os sensores com falha em 'sensor_errors'.")
        for sensor in self.sensor_errors:
            if any(getattr(self, f) is not None for f in _SENSOR_FIELDS[sensor]):
                raise ValueError(f"Sensor '{sensor}' está em 'sensor_errors' mas enviou valores.")
        return self


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: str
    timestamp: UtcDatetime
    received_at: UtcDatetime
    source: Literal["hardware", "simulated"]
    temperature_c: float | None
    humidity_pct: float | None
    pressure_hpa: float | None
    bmp280_temperature_c: float | None
    mq135_raw: int | None
    ldr_raw: int | None
    sensor_errors: list[str]

    @field_validator("sensor_errors", mode="before")
    @classmethod
    def _split(cls, v):
        if isinstance(v, str):
            return [s for s in v.split(",") if s]
        return v


class IngestOut(BaseModel):
    status: Literal["created", "duplicate"]
    reading: ReadingOut


class Trend(BaseModel):
    direction: Literal["up", "down", "flat"]
    delta: float
    window_minutes: int


class LatestOut(BaseModel):
    source: Literal["hardware", "simulated"]
    reading: ReadingOut | None
    trends: dict[str, Trend | None]


class ReadingsPage(BaseModel):
    items: list[ReadingOut]
    total: int
    page: int
    page_size: int
    pages: int


class SeriesPoint(BaseModel):
    t: UtcDatetime
    temperature_c: float | None = None
    humidity_pct: float | None = None
    pressure_hpa: float | None = None
    mq135_raw: float | None = None
    ldr_raw: float | None = None


class SeriesOut(BaseModel):
    source: Literal["hardware", "simulated"]
    period: str
    count: int
    points: list[SeriesPoint]
