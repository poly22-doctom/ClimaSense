"""Engine/sessões SQLAlchemy. Trocar SQLite por MySQL exige só alterar DATABASE_URL."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(url: str) -> Engine:
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Cria as tabelas. Para evolução de esquema em produção, use Alembic (ver README)."""
    from app import models  # noqa: F401  (registra os modelos)

    Base.metadata.create_all(engine)
    _add_missing_station_columns(engine)


# Colunas adicionadas depois da primeira versão. create_all() não altera tabelas que já existem,
# então bancos criados antes recebem as colunas novas aqui (ALTER TABLE funciona em SQLite e MySQL).
_STATION_GEO_COLUMNS = {"latitude": "FLOAT", "longitude": "FLOAT", "coverage_radius_km": "FLOAT"}


def _add_missing_station_columns(engine: Engine) -> None:
    insp = inspect(engine)
    if "stations" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("stations")}
    with engine.begin() as conn:
        for name, ddl in _STATION_GEO_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE stations ADD COLUMN {name} {ddl}"))
