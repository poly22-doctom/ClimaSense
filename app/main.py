"""Ponto de entrada: monta a aplicação FastAPI (padrão application factory)."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import analysis, health, pages, readings, station
from app.core.config import Settings, get_settings
from app.database.connection import build_engine, build_session_factory, init_db
from app.repositories import readings as repo
from app.services import simulator

log = logging.getLogger("app")
BASE_DIR = Path(__file__).resolve().parent
MAX_BODY_BYTES = 8 * 1024
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        with session_factory() as db:
            repo.upsert_station(db, settings.station_id, settings.station_name, settings.station_location)
            repo.get_alert_settings(db, settings.station_id)
        task = None
        if settings.demo_mode:
            # Uma única tarefa por processo (o lifespan roda uma vez por inicialização).
            task = asyncio.create_task(simulator.run_simulator(session_factory, settings))
            app.state.simulator_task = task
            log.warning("MODO DEMONSTRAÇÃO ativo: dados simulados serão gerados.")
        yield
        if task:
            task.cancel()
        engine.dispose()

    app = FastAPI(
        title="Estação Meteorológica e Ambiental — API", version="1.0.0", lifespan=lifespan,
        description="API REST para receber leituras do ESP32 e alimentar o painel público.",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory

    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def protect(request: Request, call_next):
        # Rejeita corpos grandes demais antes de processar
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Corpo da requisição grande demais."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path not in DOCS_PATHS:  # Swagger usa scripts de CDN/inline
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
            )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Não devolve o valor enviado (pode conter NaN/lixo); informa só campo e motivo.
        erros = [{"campo": ".".join(str(x) for x in e["loc"] if x != "body"), "mensagem": e["msg"]} for e in exc.errors()]
        return JSONResponse({"detail": "Dados inválidos.", "erros": erros}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Erro não tratado em %s %s", request.method, request.url.path)  # detalhes só no log
        return JSONResponse({"detail": "Erro interno do servidor."}, status_code=500)

    for r in (health.router, station.router, readings.router, analysis.router):
        app.include_router(r)
    app.include_router(pages.router)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    return app


app = create_app()
