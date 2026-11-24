from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.timeutils import iso_z, utcnow

router = APIRouter(prefix="/api", tags=["Saúde"])


@router.get("/health", summary="Verifica a saúde da aplicação")
def health(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        banco = "ok"
    except Exception:
        banco = "erro"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if banco == "ok" else "degradado", "database": banco, "time": iso_z(utcnow())}
