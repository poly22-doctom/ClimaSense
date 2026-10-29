from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class AlertSettings(Base):
    """Limites de alerta por estação. Valores iniciais são DEFINIÇÕES DO PROJETO, não normas oficiais."""

    __tablename__ = "alert_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("stations.station_id"), unique=True)
    temp_min_c: Mapped[float] = mapped_column(Float, default=10.0)
    temp_max_c: Mapped[float] = mapped_column(Float, default=35.0)
    humidity_min_pct: Mapped[float] = mapped_column(Float, default=30.0)
    humidity_max_pct: Mapped[float] = mapped_column(Float, default=80.0)
    pressure_change_hpa_3h: Mapped[float] = mapped_column(Float, default=3.0)
    mq135_change_pct: Mapped[float] = mapped_column(Float, default=25.0)
    offline_after_minutes: Mapped[int] = mapped_column(Integer, default=15)
