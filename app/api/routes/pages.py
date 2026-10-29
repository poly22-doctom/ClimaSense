from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import get_settings_dep
from app.core.config import Settings

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, settings: Settings = Depends(get_settings_dep)):
    return templates.TemplateResponse(request, "index.html", {"station_name": settings.station_name})
