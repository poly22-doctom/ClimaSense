from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutils import utcnow
from app.database.connection import Base

SOURCE_HARDWARE = "hardware"
SOURCE_SIMULATED = "simulated"


class Reading(Base):
    """Uma medição. Campos nulos = sensor sem leitura (ver `sensor_errors`)."""

    __tablename__ = "readings"
    __table_args__ = (
        # Reenvios da mesma medição não geram duplicatas.
        UniqueConstraint("station_id", "timestamp", "source", name="uq_reading_station_ts_source"),
        Index("ix_readings_station_source_ts", "station_id", "source", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[str] = mapped_column(String(64), ForeignKey("stations.station_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime)  # instante da medição (UTC)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source: Mapped[str] = mapped_column(String(16))  # "hardware" | "simulated"

    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)  # DHT22
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # DHT22
    pressure_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)  # BMP280
    bmp280_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)  # auxiliar
    mq135_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ADC bruto
    ldr_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ADC bruto
    sensor_errors: Mapped[str] = mapped_column(String(64), default="")  # "dht22,mq135"
