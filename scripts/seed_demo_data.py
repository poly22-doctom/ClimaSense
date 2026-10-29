"""Gera (ou apaga) dados SIMULADOS no banco configurado.

Uso (na raiz do projeto):
    python -m scripts.seed_demo_data --days 30
    python -m scripts.seed_demo_data --purge     # apaga somente registros simulados
"""
import argparse

from sqlalchemy import delete

from app.core.config import get_settings
from app.database.connection import build_engine, build_session_factory, init_db
from app.models import Reading
from app.repositories import readings as repo
from app.services import simulator


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=None, help="Dias de histórico simulado")
    p.add_argument("--purge", action="store_true", help="Remove os registros simulados")
    a = p.parse_args()

    s = get_settings()
    if a.days:
        s.simulation_backfill_days = a.days
    engine = build_engine(s.database_url)
    init_db(engine)
    sf = build_session_factory(engine)
    with sf() as db:
        repo.upsert_station(db, s.station_id, s.station_name, s.station_location)
        if a.purge:
            n = db.execute(delete(Reading).where(Reading.source == "simulated")).rowcount
            db.commit()
            print(f"{n} registro(s) simulado(s) removido(s). Registros reais não foram alterados.")
            return
    print(f"{simulator.generate_missing(sf, s)} registro(s) SIMULADO(S) gravado(s).")


if __name__ == "__main__":
    main()
