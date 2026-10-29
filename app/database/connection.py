"""Engine/sessões SQLAlchemy. Trocar SQLite por MySQL exige só alterar DATABASE_URL."""
from sqlalchemy import create_engine
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
